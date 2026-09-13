"""Bounded completion rollouts. Simulated beliefs never replace hard state.

All pseudo-observations use samples of the current feasible cells, not simulator
truth. Two sequential observations update a compact outer grid. The residual
cost after that horizon is explicitly a heuristic, not a completion certificate.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import math

import numpy as np

from .channel_state import ChannelState, ChannelStatus, Observation
from .config import PhysicalConfig, PlannerConfig
from .dynamic_open_route import (DynamicOpenRoutePlanner, OpenRoute, RouteNode,
                                 RouteNodeKind, ServiceTarget, SourceResolver)
from .geometry import CellGrid, EnclosingCircle, bearing_deg, max_distance_to_cells
from .opportunity_planner import OpportunityPlanner


def outer_box_circle(grid: CellGrid, mask: np.ndarray) -> EnclosingCircle:
    cells = grid.centers[mask]
    if not len(cells):
        return EnclosingCircle(np.zeros(2), math.inf)
    lo, hi = cells.min(axis=0)-grid.half_m, cells.max(axis=0)+grid.half_m
    return EnclosingCircle((lo+hi)/2, float(np.linalg.norm(hi-lo))/2+1e-8)


def guaranteed_reception(state: ChannelState, point: np.ndarray) -> bool:
    """A sufficient test for every point of the union of closed cells."""
    cells = state.grid.centers[state.possible]
    return bool(len(cells) and np.max(max_distance_to_cells(
        point, cells, state.grid.half_m)) <= state.physical.reception_min_m)


def posterior_weights(state: ChannelState, points: np.ndarray) -> np.ndarray:
    """Soft ranking under uniform-area / uniform-receiver-radius assumptions.

    A source has ONE fixed unknown reception radius. Integrate its feasible
    interval rather than multiplying independent per-observation probabilities.
    Cell centers are quadrature samples only: these weights never prune cells.
    """
    low=np.full(len(points),state.physical.reception_min_m)
    high=np.full(len(points),state.physical.reception_max_m)
    feasible=np.linalg.norm(points,axis=1)<=state.physical.target_radius_m
    for obs in state.history:
        delta=points-np.asarray(obs.position)
        distance=np.linalg.norm(delta,axis=1)
        if obs.result in ('direction','near'):
            low=np.maximum(low,distance)
        elif obs.result=='no_signal':
            high=np.minimum(high,distance)
        if obs.result=='direction':
            angle=np.degrees(np.arctan2(delta[:,1],delta[:,0]))
            error=np.abs((angle-float(obs.bearing_deg)+180.)%360.-180.)
            feasible &= error<=state.physical.bearing_error_deg+state.bearing_tolerance_extra_deg
    weights=np.maximum(0.,high-low)*feasible
    if not np.any(weights):
        # A very thin continuous set can miss every cell center. That is a
        # quadrature failure, not an absence or a reason to discard hard cells.
        weights=np.ones(len(points))
    return weights/weights.sum()


class RegionOpportunityPlanner(OpportunityPlanner):
    def reception_class(self, state, point):
        original = super().reception_class(state, point)
        if original == 'possible' and guaranteed_reception(state, point):
            return 'guaranteed'
        return original

    def _measurement_point(self, state, leg, radius_m, *, possible=False):
        # Keep the original candidate, then also search outside the inscribed
        # MEC reception disk. Each added point passes a full outer-cell test.
        old = super()._measurement_point(state, leg, radius_m, possible=possible)
        if possible:
            return old
        for fraction in np.linspace(0, 1, 25):
            point = leg.start + fraction*(leg.end-leg.start)
            if old is not None and fraction >= old[1]:
                break
            if state.already_measured(point):
                continue
            baseline, gain = self.measurement_geometry(state, point)
            if (baseline >= self.planner.minimum_view_baseline_m
                    and gain >= self.planner.opportunity_target_angle_deg
                    and guaranteed_reception(state, point)):
                return point, float(fraction)
        return old


@dataclass(frozen=True)
class CompletionEstimate:
    endpoint: np.ndarray
    additional_cost_s: float
    risk_s: float
    sample_count: int
    remaining_radius_m: float


@dataclass(frozen=True)
class CompletionNode(RouteNode):
    predicted_endpoint: np.ndarray | None = None
    additional_cost_s: float = 0.0
    alternatives: tuple = ()


class CompletionResolver(SourceResolver):
    def __init__(self, physical: PhysicalConfig, planner: PlannerConfig):
        super().__init__(physical, planner)
        self.estimates: dict[int, CompletionEstimate] = {}
        self.alternatives: dict[int, list[tuple[np.ndarray, CompletionEstimate]]] = {}
        self.trace: list[dict] = []
        self._cache: dict[tuple, CompletionEstimate] = {}
        self._sample_cache: dict[tuple,np.ndarray] = {}

    def _predict(self, state: ChannelState, point: np.ndarray) -> CompletionEstimate:
        # Restrict simulated computation to currently retained cells. No write
        # to state.possible, history, certificate or channel lifecycle occurs.
        key = (state.channel, len(state.history), state.clear_failures,
               state.grid.step_m, state.possible_count, *np.round(point, 5))
        if key in self._cache:
            return self._cache[key]
        grid = CellGrid(state.grid.centers[state.possible].copy(),
                        state.grid.step_m, state.grid.target_radius_m)
        count = min(self.planner.completion_sample_count, len(grid.centers))
        if count == 0:
            raise ValueError('cannot preview an empty found-source belief')
        sample_key=key[:5]
        if sample_key not in self._sample_cache:
            rng = np.random.default_rng(self.planner.seed + state.channel*1009 + len(state.history))
            weights=posterior_weights(state,grid.centers) if self.planner.posterior_completion else None
            if weights is not None:
                count=min(count,int(np.count_nonzero(weights)))
            self._sample_cache[sample_key]=grid.centers[np.sort(rng.choice(
                len(grid.centers),count,replace=False,p=weights))]
        samples=self._sample_cache[sample_key]
        costs, ends, radii = [], [], []
        for sample in samples:
            for error in (-0.8, 0.0, 0.8):
                mask = grid.all_mask()
                p = point.copy()
                cost = 0.0
                radius = state.certificate().radius_m
                simulated=copy.copy(state)
                simulated.history=list(state.history)
                trials=int(getattr(state,'optical_trial_count',0))
                for depth in range(2):
                    if np.linalg.norm(sample-p) <= self.physical.near_radius_m:
                        cost += self.physical.optical_s+self.physical.laser_s
                        radius = 0.0
                        break
                    # Dedicated candidate points are guaranteed reception. The
                    # second point is a posterior center; include no-signal if
                    # the conservative sample lies beyond the minimum range.
                    if np.linalg.norm(sample-p) > self.physical.reception_min_m:
                        keep = grid.no_signal_keep_mask(p, self.physical.reception_min_m)
                        simulated.history.append(Observation(tuple(p),'no_signal'))
                    else:
                        observed=bearing_deg(p,sample)+error
                        keep = grid.direction_keep_mask(
                            p, observed,
                            self.physical.bearing_error_deg+state.bearing_tolerance_extra_deg,
                            self.physical.reception_max_m, self.physical.near_radius_m)
                        simulated.history.append(Observation(tuple(p),'direction',observed))
                    proposed = mask & keep
                    if np.any(proposed):
                        mask = proposed
                    circle = outer_box_circle(grid, mask)
                    radius = circle.radius_m
                    goal=circle.center
                    trial=False
                    if (self.planner.posterior_clear_rollout
                            and self.physical.clear_radius_m-self.planner.clear_margin_m<radius<=self.planner.optical_probe_radius_m
                            and trials<self.planner.optical_probe_limit):
                        cells=grid.centers[mask]
                        weights=posterior_weights(simulated,cells)
                        goal=np.average(cells,axis=0,weights=weights)
                        occupancy=weights[np.linalg.norm(cells-goal,axis=1)<=self.physical.clear_radius_m].sum()
                        trial=occupancy>=self.planner.optical_probe_min_fraction
                    cost += float(np.linalg.norm(goal-p))/self.physical.speed_mps
                    p = goal
                    if radius <= self.physical.clear_radius_m-self.planner.clear_margin_m:
                        cost += self.physical.optical_s+self.physical.laser_s
                        break
                    if trial:
                        trials+=1
                        cost+=self.physical.optical_s
                        if np.linalg.norm(sample-p)<=self.physical.clear_radius_m:
                            cost+=self.physical.laser_s
                            radius=0.
                            break
                        proposed=mask & grid.failed_clear_keep_mask(p,self.physical.clear_radius_m)
                        if np.any(proposed):
                            mask=proposed
                        radius=outer_box_circle(grid,mask).radius_m
                    if depth == 0:
                        cost += self.physical.measure_s
                    else:
                        # Residual terminal value, not a simulated successful
                        # clear: price another view and a conservative approach.
                        cost += self.physical.measure_s+5.0+2.0*radius/self.physical.speed_mps
                costs.append(cost)
                ends.append(p.copy())
                radii.append(radius)
        estimate = CompletionEstimate(np.mean(ends, axis=0), float(np.mean(costs)),
            max(0.0, float(np.quantile(costs, .9)-np.mean(costs))), len(costs),
            float(np.mean(radii)))
        if len(self._cache) > 4096:
            self._cache.clear()
        self._cache[key] = estimate
        return estimate

    def current_service_target(self, state, current_position, coverage, remaining_vertices):
        legacy = super().current_service_target(state, current_position, coverage, remaining_vertices)
        self.estimates.pop(state.channel, None)
        self.alternatives.pop(state.channel, None)
        if legacy is None and state.status == ChannelStatus.FOUND:
            # Exhausting a finite candidate list must not strand a source.
            # The covering queue is a conservative termination fallback even
            # if fewer than six distinct bearings have been obtained.
            state.activate_fallback(current_position)
            if state.fallback_queue:
                points=np.asarray(state.fallback_queue,float)
                point=points[int(np.argmin(np.linalg.norm(points-current_position,axis=1)))]
                return ServiceTarget(point.copy(),'CLEAR','conservative_fallback',self.physical.optical_s)
        if legacy is None or legacy.action != 'MEASURE' or legacy.reason == 'preplanned_cross_view':
            return legacy
        circle = state.certificate()
        if not self.planner.completion_lookahead:
            return legacy
        if remaining_vertices and not state.tsp_window_armed:
            return legacy
        p = np.asarray(current_position, float)
        following = coverage[remaining_vertices[0]] if remaining_vertices else None
        raw = [legacy.point, circle.center]
        if self.planner.posterior_completion:
            cells=state.grid.centers[state.possible]
            raw.append(np.average(cells,axis=0,weights=posterior_weights(state,cells)))
        # Near-center choices trade angular information against the entire
        # approach, instead of lexicographically preferring radial motion.
        ray = p-circle.center
        norm = float(np.linalg.norm(ray))
        if norm > 1e-8:
            unit = ray/norm
            normal = np.array([-unit[1], unit[0]])
            for radius in (80., 200., 400.):
                for sign in (-1., 1.):
                    raw.append(circle.center+radius*(.70710678*unit+sign*.70710678*normal))
        raw.append(p)
        if following is not None:
            delta = following-p
            length2 = float(np.dot(delta, delta))
            f = float(np.clip(np.dot(circle.center-p, delta)/max(length2, 1e-9), 0, 1))
            raw.extend((p+f*delta, following))
        candidates, seen = [], set()
        for point in raw:
            point = np.asarray(point, float)
            k = tuple(np.round(point, 5))
            if k in seen or state.already_measured(point):
                continue
            seen.add(k)
            if np.linalg.norm(point) > self.physical.target_radius_m:
                continue
            if not guaranteed_reception(state, point):
                continue
            estimate = self._predict(state, point)
            score = float(np.linalg.norm(point-p))/self.physical.speed_mps + 5 + estimate.additional_cost_s
            score += self.planner.tail_weight*estimate.risk_s
            if following is not None:
                score += float(np.linalg.norm(following-estimate.endpoint))/self.physical.speed_mps
            candidates.append((score, k, point, estimate))
        if not candidates:
            return legacy
        score, _key, selected, estimate = min(candidates, key=lambda x:(x[0],x[1]))
        self.estimates[state.channel] = estimate
        self.alternatives[state.channel] = [(item[2].copy(),item[3])
            for item in sorted(candidates,key=lambda x:(x[0],x[1]))[:4]]
        self.trace.append({'channel':state.channel, 'candidates':len(candidates),
            'estimated_cost_with_next_anchor_s':score,
            'predicted_endpoint':estimate.endpoint.tolist(),
            'additional_cost_s':estimate.additional_cost_s,
            'risk_s':estimate.risk_s, 'sample_count':estimate.sample_count,
            'selected_point':selected.tolist(), 'certainty':'estimated_two_observation_rollout'})
        return ServiceTarget(selected.copy(), 'MEASURE', 'completion_service', self.physical.measure_s)


class CompletionRoutePlanner(DynamicOpenRoutePlanner):
    """Interface-correct channel transitions plus estimated service endpoints."""
    def _allowed(self,index,mask,nodes):
        return self.planner.free_coverage_order or super()._allowed(index,mask,nodes)

    @staticmethod
    def endpoint(node):
        point = getattr(node, 'predicted_endpoint', None)
        return node.point if point is None else point

    @staticmethod
    def next_channel(node, channel):
        return node.channel if node.action == 'MEASURE' and node.channel is not None else channel

    def _step_cost(self, start, node, channel):
        movement = float(np.linalg.norm(node.point-start))/self.physical.speed_mps
        switch = self.physical.switch_s if self.next_channel(node, channel) != channel else 0.
        return movement+switch+node.operation_cost_s+getattr(node,'additional_cost_s',0.)

    def plan(self, start, current_channel, nodes):
        route=super().plan(start,current_channel,nodes)
        if not self.planner.joint_service_alternatives or not route.nodes:
            return route
        # Coordinate descent over a fixed route, then reorder the selected
        # options. At most two passes, always retain the previous cheaper plan.
        # Every source remains one obligation; alternatives are not extra tasks.
        for _pass in range(2):
            selected=list(route.nodes)
            changed=False
            point=start
            channel=current_channel
            for i,node in enumerate(selected):
                options=getattr(node,'alternatives',())
                following=selected[i+1] if i+1<len(selected) else None
                def local_cost(option):
                    value=self._step_cost(point,option,channel)
                    if following is not None:
                        value+=self._step_cost(self.endpoint(option),following,
                                              self.next_channel(option,channel))
                    return value
                best=node
                cost=local_cost(node)
                for option in options:
                    value=local_cost(option)
                    if value<cost-1e-8:
                        best,cost=option,value
                if best is not node:
                    from dataclasses import replace
                    best=replace(best,alternatives=options)
                    selected[i]=best
                    changed=True
                point=self.endpoint(best)
                channel=self.next_channel(best,channel)
            if not changed:
                break
            candidate=super().plan(start,current_channel,selected)
            if candidate.cost_s>=route.cost_s-1e-8:
                break
            route=candidate
        # 'exact' only describes ordering with fixed options, not the joint
        # neighborhood problem. Joint plans are explicitly heuristic.
        from dataclasses import replace
        return replace(route,exact=False)

    def _exact(self, start, current_channel, nodes):
        # One frontier per subset size avoids rescanning all smaller subsets.
        frontier = {(0, -1, current_channel):(0., 0., ())}
        for _size in range(len(nodes)):
            following = {}
            for (mask,last,channel),(cost,distance,order) in frontier.items():
                point = start if last < 0 else self.endpoint(nodes[last])
                for i,node in enumerate(nodes):
                    if mask & (1 << i) or not self._allowed(i,mask,nodes):
                        continue
                    key=(mask | (1 << i),i,self.next_channel(node,channel))
                    value=(cost+self._step_cost(point,node,channel),
                           distance+float(np.linalg.norm(node.point-point)),order+(i,))
                    if key not in following or (value[0],value[2]) < (following[key][0],following[key][2]):
                        following[key]=value
            frontier=following
        cost,distance,order=min(frontier.values(),key=lambda v:(v[0],v[2]))
        return OpenRoute(tuple(nodes[i] for i in order),cost,distance,True)

    def _score_order(self,start,channel,nodes,order):
        cost=distance=0.
        for i in order:
            node=nodes[i]
            cost+=self._step_cost(start,node,channel)
            distance+=float(np.linalg.norm(node.point-start))
            start=self.endpoint(node)
            channel=self.next_channel(node,channel)
        return cost,distance

    def _deterministic_fallback(self,start,current_channel,nodes):
        mask=0
        point=start
        channel=current_channel
        order=[]
        while len(order)<len(nodes):
            allowed=[i for i in range(len(nodes)) if not mask&(1<<i) and self._allowed(i,mask,nodes)]
            i=min(allowed,key=lambda i:(self._step_cost(point,nodes[i],channel),nodes[i].label))
            order.append(i)
            mask|=1<<i
            point=self.endpoint(nodes[i])
            channel=self.next_channel(nodes[i],channel)
        best=self._score_order(start,current_channel,nodes,order)
        if self.planner.improve_greedy_route:
            for _pass in range(2):
                winner=order
                for a in range(len(order)):
                    for b in range(len(order)):
                        proposal=order.copy()
                        proposal.insert(b,proposal.pop(a))
                        anchors=[nodes[i].vertex for i in proposal if nodes[i].kind==RouteNodeKind.COVERAGE]
                        if not self.planner.free_coverage_order and anchors != sorted(anchors):
                            continue
                        score=self._score_order(start,current_channel,nodes,proposal)
                        if score[0] < best[0]-1e-8:
                            best,winner=score,proposal
                if winner == order:
                    break
                order=winner
        return OpenRoute(tuple(nodes[i] for i in order),*best,False)
