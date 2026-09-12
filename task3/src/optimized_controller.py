"""Opt-in Q3 optimization experiments on top of the frozen 041 controller."""

from __future__ import annotations

from dataclasses import replace
import numpy as np

from .channel_state import ChannelStatus
from .completion_planner import (CompletionNode, CompletionResolver,
    CompletionRoutePlanner, RegionOpportunityPlanner, guaranteed_reception, posterior_weights)
from .dynamic_open_route import (build_candidate_nodes, localization_stage, LocalizationStage,
                                GuardDecision, GuardLevel)
from .dynamic_open_route_controller import DynamicOpenRouteController
from .geometry import CellGrid, max_distance_to_cells
from .opportunity_planner import EmbeddedEvent, EmbeddedEventKind


class OptimizedController(DynamicOpenRouteController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resolver = CompletionResolver(self.physical, self.planner)
        self.open_route_planner = CompletionRoutePlanner(self.physical, self.planner)
        if self.planner.exact_reception_region:
            self.opportunity_planner = RegionOpportunityPlanner(self.physical, self.planner)
        self.retired_vertices: set[int] = set()
        self.probe_attempts: dict[int,int] = {}
        self._operation_id = 0
        self._pending_predictions: dict[int,dict] = {}
        self.enroute_probe_positions: dict[int,list[np.ndarray]] = {}
        self.enroute_probe_count = 0
        self.shared_search_count = 0
        if self.planner.adaptive_anchor_positions and not (
                self.planner.free_coverage_order and self.planner.adaptive_search_certificate):
            raise ValueError('moving anchors requires free order and per-channel adaptive search certificates')

    def _refresh_tsp_window(self,state):
        if self.planner.free_coverage_order and state.status==ChannelStatus.FOUND:
            state.tsp_window_armed=True
            return
        super()._refresh_tsp_window(state)

    def _check_guard(self,position,first):
        if self.planner.free_coverage_order:
            # This policy has no angular scheduling obligations. Full search
            # still requires the same certified seven-point covering set;
            # safe local actions and finite fallback do not depend on order.
            return GuardDecision(GuardLevel.NONE,None,first,None,None,0.)
        return super()._check_guard(position,first)

    def _opportunity_events(self,start,target,guard,excluded_measure_channels=None):
        events=super()._opportunity_events(start,target,guard,excluded_measure_channels)
        if self.enroute_probe_count>=self.planner.opportunistic_probe_budget:
            return events
        delta=target.point-start
        length2=float(np.dot(delta,delta))
        if length2<=1e-8:
            return events
        for channel,state in self.channels.items():
            tried=self.enroute_probe_positions.get(channel,[])
            if (state.status!=ChannelStatus.FOUND or state.safe_clear_point() is not None
                    or len(tried)>=self.planner.opportunistic_probe_source_limit):
                continue
            cells=state.grid.centers[state.possible]
            weights=posterior_weights(state,cells) if self.planner.posterior_completion else None
            projection=np.clip((cells-start)@delta/length2,0.,1.)
            fractions=np.unique(np.quantile(projection,np.linspace(.1,.9,9)))
            circle=state.certificate()
            candidates=[]
            for fraction in fractions:
                point=start+fraction*delta
                if np.linalg.norm(point-start)<self.planner.min_opportunistic_event_distance_m:
                    continue
                if any(np.linalg.norm(point-old)<30. for old in tried):
                    continue
                inside=np.linalg.norm(cells-point,axis=1)<=self.physical.clear_radius_m
                fraction_inside=float(np.mean(inside) if weights is None else weights[inside].sum())
                if fraction_inside<=0:
                    continue
                # Aggressive expected-value surrogate: cell occupancy is a
                # ranking assumption, never a success certificate. Price the
                # uncertain local approach plus an extra view that a hit avoids.
                saved_if_hit=2.*circle.radius_m/self.physical.speed_mps+self.physical.measure_s
                estimate=self.resolver.estimates.get(channel)
                if estimate is not None:
                    saved_if_hit=max(saved_if_hit,estimate.additional_cost_s+self.physical.measure_s)
                gain=fraction_inside*saved_if_hit-(1-fraction_inside)*self.physical.optical_s
                if gain>=self.planner.opportunistic_probe_min_gain_s:
                    candidates.append((gain,float(fraction),point,fraction_inside))
            if candidates:
                gain,fraction,point,occupancy=max(candidates,key=lambda item:(item[0],-item[1]))
                events.append(EmbeddedEvent(point,channel,EmbeddedEventKind.CLEAR,
                    'opportunistic_optical_probe',fraction,'heuristic_occupancy'))
        return sorted(events,key=lambda event:(event.leg_fraction,event.kind!=EmbeddedEventKind.CLEAR,event.channel))

    def _execute_embedded(self,event,guard_channel):
        if event.reason!='opportunistic_optical_probe':
            return super()._execute_embedded(event,guard_channel)
        self.enroute_probe_count+=1
        self.enroute_probe_positions.setdefault(event.channel,[]).append(event.position.copy())
        self._record_clear(event.position,event.channel,event.reason,certified=False)
        success=self.channels[event.channel].status==ChannelStatus.CLEARED
        self._last_embedded_causes_replan=success
        self.diagnostics.append({'type':'bounded_enroute_probe','channel':event.channel,
            'attempt':self.enroute_probe_count,'success':success,
            'budget':self.planner.opportunistic_probe_budget,
            'position':event.position.tolist()})
        return 'enroute_probe_cleared' if success else 'enroute_probe_missed'

    def _measure(self, point, channel, coverage_index=None):
        state = self.channels[channel]
        if state.already_measured(point):
            return
        self._operation_id += 1
        operation_id = self._operation_id
        before_time = self.client.last_virtual_time_s
        before_position = np.asarray(self.client.position,float).copy()
        before_channel = self.client.current_channel
        super()._measure(point, channel, coverage_index)
        near = state.history[-1].result == 'near'
        end_time = self.client.last_virtual_time_s
        if near:
            # The nested clear can also report an unexpected miss. Use the
            # actual boundary between operations instead of assuming 5 s.
            clear = next(d for d in reversed(self.diagnostics)
                         if d['type']=='actual_operation' and d['operation_id']==operation_id+1)
            end_time = clear['start_time_s']
        self.diagnostics.append({'type':'actual_operation','operation_id':operation_id,
            'action':'MEASURE','channel':channel,'position':np.asarray(point).tolist(),
            'start_position':before_position.tolist(),'start_time_s':before_time,
            'end_time_s':end_time,'cost_s':end_time-before_time,
            'switched':before_channel!=channel,'result':state.history[-1].result})
        self._update_absence_certificates()

    def _clear(self, point, channel, certified, source):
        self._operation_id += 1
        operation_id = self._operation_id
        before_time = self.client.last_virtual_time_s
        start = np.asarray(self.client.position,float).copy()
        super()._clear(point,channel,certified,source)
        cleared = self.channels[channel].status == ChannelStatus.CLEARED
        self.diagnostics.append({'type':'actual_operation','operation_id':operation_id,
            'action':'CLEAR','channel':channel,'position':np.asarray(point).tolist(),
            'start_position':start.tolist(),'start_time_s':before_time,
            'end_time_s':self.client.last_virtual_time_s,
            'cost_s':self.client.last_virtual_time_s-before_time,
            'certified':certified,'reason':source,'success':cleared})
        if cleared and channel in self._pending_predictions:
            prior=self._pending_predictions.pop(channel)
            self.diagnostics.append({'type':'completion_prediction_outcome','channel':channel,
                **prior,'first_plan_to_clear_elapsed_s':self.client.last_virtual_time_s-prior['start_time_s'],
                'attributed_channel_action_cost_s':sum(d['cost_s'] for d in self.diagnostics
                    if d['type']=='actual_operation' and d['channel']==channel
                    and d['operation_id']>prior['start_operation_id']),
                'comparison_note':'elapsed includes interleaved work; attributed costs include approach legs',
                'actual_completion_position':np.asarray(point).tolist(),
                'endpoint_error_m':float(np.linalg.norm(np.asarray(point)-prior['predicted_endpoint']))})

    def _update_absence_certificates(self):
        found = sum(s.status in (ChannelStatus.FOUND,ChannelStatus.CLEARED) for s in self.channels.values())
        for state in self.channels.values():
            if state.status != ChannelStatus.UNKNOWN:
                continue
            reason = None
            if self.planner.focus_after_upper_bound_discovered and found == self.physical.max_sources:
                reason='distinct_discoveries_reach_upper_bound'
            elif self.planner.adaptive_search_certificate and state.possible_count == 0:
                reason='empty_outer_unknown_set'
            if reason:
                state.status=ChannelStatus.ABSENT
                self.diagnostics.append({'type':'absence_certificate','channel':state.channel,'reason':reason})

    def _search_complete(self):
        return super()._search_complete() or not any(
            s.status == ChannelStatus.UNKNOWN for s in self.channels.values())

    def _scan_unknown_coverage(self,index):
        point=self.coverage[index]
        unknown=[c for c,s in self.channels.items() if s.status==ChannelStatus.UNKNOWN]
        if self.client.current_channel in unknown:
            unknown.remove(self.client.current_channel)
            unknown.insert(0,self.client.current_channel)
        for channel in unknown:
            if self.channels[channel].status==ChannelStatus.UNKNOWN:
                self._record_measure(point,channel,'coverage_unknown_scan',coverage_index=index)
        revisit=[]
        for channel,state in self.channels.items():
            if state.status!=ChannelStatus.FOUND or state.safe_clear_point() is not None:
                continue
            if index not in self._origin_revisit_vertices(state) or state.already_measured(point):
                continue
            reception=self.opportunity_planner.reception_class(state,point)
            baseline,gain=self.opportunity_planner.measurement_geometry(state,point)
            if reception=='impossible' or (reception=='possible' and (
                    baseline<self.planner.minimum_view_baseline_m or gain<self.planner.minimum_view_angle_gain_deg)):
                continue
            priority=0 if localization_stage(state,self.planner)==LocalizationStage.BROAD else 1
            revisit.append((priority,-gain,-baseline,channel,reception,baseline,gain))
        for _,_,_,channel,reception,baseline,gain in sorted(revisit)[:self.planner.coverage_revisit_limit]:
            direction=self._record_measure(point,channel,'coverage_found_revisit',coverage_index=index,
                reception_class=reception,baseline_m=baseline,view_angle_gain_deg=gain)
            self.coverage_revisit_count+=1
            if direction:
                self.coverage_revisit_direction_count+=1
                self._coverage_revisit_directions_by_channel[channel]=self._coverage_revisit_directions_by_channel.get(channel,0)+1
        self.coverage_completed.add(index)
        for state in self.channels.values():
            if not self.planner.adaptive_anchor_positions:
                state.mark_absent_if_covered(len(self.coverage))
        self._update_absence_certificates()
        self.diagnostics.append({'type':'coverage_completed','coverage_index':index,
            'position':point.tolist(),'completion_order':sorted(self.coverage_completed-{0})})

    def _refine(self,state):
        if not self.planner.refine_certificate or state.grid.step_m<=1.25:
            return
        if not self.physical.clear_radius_m-self.planner.clear_margin_m < state.certificate().radius_m <= 40.0:
            return
        old_grid,old_mask=state.grid,state.possible
        parents=old_grid.centers[old_mask]
        offset=old_grid.step_m/4
        children=(parents[:,None,:]+np.array([[-offset,-offset],[-offset,offset],
                     [offset,-offset],[offset,offset]])[None,:,:]).reshape(-1,2)
        state.grid=CellGrid(children,old_grid.step_m/2,old_grid.target_radius_m)
        mask=state.grid.all_mask()
        for obs in state.history:
            mask &= state._mask_for(obs)
        if not np.any(mask):
            state.grid,state.possible=old_grid,old_mask
            self.diagnostics.append({'type':'refinement_rejected_empty','channel':state.channel})
            return
        state.possible=mask
        state._certificate_cache=None
        state.fallback_queue.clear()
        self.diagnostics.append({'type':'local_cell_refinement','channel':state.channel,
            'old_step_m':old_grid.step_m,'new_step_m':state.grid.step_m,
            'cells':state.possible_count,'radius_m':state.certificate().radius_m})

    def _remaining_vertices(self):
        return [i for i in range(1,len(self.coverage))
                if i not in self.coverage_completed and i not in self.retired_vertices]

    def _unknown_union(self):
        states=[s for s in self.channels.values() if s.status==ChannelStatus.UNKNOWN]
        if not states:
            return np.empty((0,2))
        # Unknown states are never locally refined.
        mask=np.logical_or.reduce([s.possible for s in states])
        return self.grid.centers[mask]

    def _retire_redundant_vertices(self):
        if not self.planner.adaptive_search_certificate and not self._search_complete():
            return
        remaining=self._remaining_vertices()
        cells=self._unknown_union()
        cover={i:max_distance_to_cells(self.coverage[i],cells,self.grid.half_m)
                   <= self.physical.reception_min_m for i in remaining}
        count=sum(cover.values(),np.zeros(len(cells),dtype=int))
        for i in remaining:
            if np.all(count-cover[i] > 0):
                count-=cover[i]
                self.retired_vertices.add(i)
                self.diagnostics.append({'type':'coverage_vertex_retired','vertex':i,
                    'reason':'all_unknown_cells_covered_by_remaining_anchors',
                    'unknown_union_cells':len(cells)})

    def _clear_point(self,state,point):
        if not self.planner.clear_region_routing:
            return point
        circle=state.certificate()
        limit=self.physical.clear_radius_m-self.planner.clear_margin_m
        radius=max(0.,limit-circle.radius_m)
        p=np.asarray(self.client.position,float)
        delta=p-circle.center
        distance=float(np.linalg.norm(delta))
        q=circle.center+delta*min(1.,radius/max(distance,1e-9))
        if np.max(max_distance_to_cells(q,state.grid.centers[state.possible],state.grid.half_m))<=limit:
            return q
        return point

    def _shift_coverage_anchors(self):
        if not self.planner.adaptive_anchor_positions:
            return
        remaining=self._remaining_vertices()
        cells=self._unknown_union()
        if len(remaining)<2 or not len(cells):
            return
        robot=np.asarray(self.client.position,float)
        source_centers=[s.certificate().center for s in self.channels.values()
                        if s.status==ChannelStatus.FOUND]
        cover={i:max_distance_to_cells(self.coverage[i],cells,self.grid.half_m)
                   <=self.physical.reception_min_m for i in remaining}
        count=sum(cover.values(),np.zeros(len(cells),dtype=int))
        if not np.all(count>0):
            self.diagnostics.append({'type':'anchor_shift_rejected_incomplete_outer_cover'})
            return
        for i in sorted(remaining,key=lambda i:float(np.linalg.norm(self.coverage[i]-robot)))[:2]:
            unique=cells[(count==1)&cover[i]]
            if not len(unique):
                continue
            original=self.coverage[i].copy()
            successor=min((self.coverage[j] for j in remaining if j!=i),
                          key=lambda p:float(np.linalg.norm(p-original)))
            goals=[robot,(robot+successor)/2]
            if source_centers:
                goals.append(min(source_centers,key=lambda p:float(np.linalg.norm(p-original))))
            # Improve an insertion proxy while enforcing the COMPLETE union
            # covering invariant. The proxy is not a global optimum claim.
            exits=[successor]+source_centers
            def score(point):
                return min(float(np.linalg.norm(robot-point)+np.linalg.norm(point-end)
                                 -np.linalg.norm(robot-end)) for end in exits)
            best=original
            best_cost=score(original)
            for goal in goals:
                goal=np.asarray(goal,float)
                if np.linalg.norm(goal)>self.physical.target_radius_m:
                    goal=goal*self.physical.target_radius_m/np.linalg.norm(goal)
                low,high=0.,1.
                for _ in range(16):
                    fraction=(low+high)/2
                    candidate=original+fraction*(goal-original)
                    if np.max(max_distance_to_cells(candidate,unique,self.grid.half_m))<=self.physical.reception_min_m:
                        low=fraction
                    else:
                        high=fraction
                candidate=original+low*(goal-original)
                cost=score(candidate)
                if cost<best_cost-1.:
                    best,best_cost=candidate,cost
            if np.linalg.norm(best-original)<1.:
                continue
            new_cover=max_distance_to_cells(best,cells,self.grid.half_m)<=self.physical.reception_min_m
            proposed=count-cover[i]+new_cover
            if not np.all(proposed>0):
                continue
            self.coverage[i]=best
            count=proposed
            cover[i]=new_cover
            self.diagnostics.append({'type':'coverage_anchor_shift','vertex':i,
                'old_position':original.tolist(),'position':best.tolist(),
                'outer_cells_certified':len(cells),'all_remaining_cells_covered':True,
                'unique_max_distance_m':float(np.max(max_distance_to_cells(best,unique,self.grid.half_m)))})

    def _build_route_nodes(self,**kwargs):
        for state in self.channels.values():
            if state.status==ChannelStatus.FOUND:
                self._refine(state)
                if self.planner.admit_ready_sources and state.certificate().radius_m<=self.planner.rough_localization_diameter_m/2:
                    state.tsp_window_armed=True
        self._retire_redundant_vertices()
        self._shift_coverage_anchors()
        kwargs['completed_vertices']=self.coverage_completed | self.retired_vertices
        self.resolver.trace.clear()
        nodes,anchors=build_candidate_nodes(**kwargs)
        optimized=[]
        for node in nodes:
            state=self.channels.get(node.channel)
            if state is not None and node.action=='CLEAR' and node.reason=='certified_clear_point':
                node=replace(node,point=self._clear_point(state,node.point))
            if state is not None and node.action=='MEASURE' and node.reason!='preplanned_cross_view':
                if self._probe_admissible(state,node.point):
                    node=replace(node,action='CLEAR',reason='bounded_optical_probe',operation_cost_s=5.)
                elif state.channel in self.resolver.estimates:
                    est=self.resolver.estimates[state.channel]
                    node=CompletionNode(**node.__dict__,predicted_endpoint=est.endpoint.copy(),
                        additional_cost_s=est.additional_cost_s+self.planner.tail_weight*est.risk_s,
                        alternatives=tuple(CompletionNode(**{**node.__dict__,'point':p},
                            predicted_endpoint=e.endpoint.copy(),
                            additional_cost_s=e.additional_cost_s+self.planner.tail_weight*e.risk_s)
                            for p,e in self.resolver.alternatives.get(state.channel,[])))
            optimized.append(node)
        for trace in self.resolver.trace:
            self.diagnostics.append({'type':'completion_candidate_preview',**trace})
        return optimized,anchors

    def _probe_admissible(self,state,point):
        if self.probe_attempts.get(state.channel,0)>=self.planner.optical_probe_limit:
            return False
        if state.certificate().radius_m > self.planner.optical_probe_radius_m:
            return False
        # Heuristic occupancy fraction, not a calibrated probability or a
        # safety certificate. A miss retains the deterministic fallback.
        cells=state.grid.centers[state.possible]
        inside=np.linalg.norm(cells-point,axis=1)<=self.physical.clear_radius_m
        fraction=float(posterior_weights(state,cells)[inside].sum() if self.planner.posterior_completion else np.mean(inside))
        return fraction>=self.planner.optical_probe_min_fraction

    def _shared_stop(self):
        point=np.asarray(self.client.position,float)
        if self.planner.shared_stop_measurements:
            eligible=[]
            for state in self.channels.values():
                if state.status!=ChannelStatus.FOUND or state.safe_clear_point() is not None:
                    continue
                if state.already_measured(point) or state.bearing_count>=self.planner.max_bearings_before_fallback:
                    continue
                baseline,gain=self.opportunity_planner.measurement_geometry(state,point)
                if baseline>=100 and gain>=30 and guaranteed_reception(state,point):
                    eligible.append((-gain,state.channel))
            for _,channel in sorted(eligible)[:2]:
                self._record_measure(point,channel,'shared_stop_guaranteed',reception_class='guaranteed')
        if not self.planner.adaptive_search_certificate:
            return
        # Only add unknown scans if this stop can replace an anchor's unique
        # cells and the estimated saved movement exceeds all scan costs.
        remaining=self._remaining_vertices()
        cells=self._unknown_union()
        if not len(cells) or not remaining:
            return
        reception=self.physical.reception_min_m
        at_stop=max_distance_to_cells(point,cells,self.grid.half_m)<=reception
        cover={i:max_distance_to_cells(self.coverage[i],cells,self.grid.half_m)<=reception for i in remaining}
        count=sum(cover.values(),np.zeros(len(cells),dtype=int))
        useful=False
        for index,i in enumerate(remaining):
            other=count-cover[i]
            if not np.all((other>0)|at_stop):
                continue
            previous=point if index==0 else self.coverage[remaining[index-1]]
            nextpoint=None if index+1==len(remaining) else self.coverage[remaining[index+1]]
            saving=float(np.linalg.norm(previous-self.coverage[i]))
            if nextpoint is not None:
                saving+=float(np.linalg.norm(self.coverage[i]-nextpoint)-np.linalg.norm(previous-nextpoint))
            unknown=sum(s.status==ChannelStatus.UNKNOWN and not s.already_measured(point)
                        for s in self.channels.values())
            if saving/self.physical.speed_mps>unknown*(self.physical.measure_s+self.physical.switch_s)+10:
                useful=True
                break
        if self.planner.aggressive_shared_search and self.shared_search_count<self.planner.shared_search_measurement_budget:
            fraction=float(np.mean(at_stop))
            # Pay for partial new coverage, even before one whole anchor can
            # be retired. All changes to unknown state still need real scans.
            if fraction>=self.planner.shared_search_min_fraction:
                useful=True
        if useful:
            for channel in sorted(self.channels):
                state=self.channels[channel]
                if state.status==ChannelStatus.UNKNOWN and not state.already_measured(point):
                    if (self.planner.aggressive_shared_search and
                            self.shared_search_count>=self.planner.shared_search_measurement_budget):
                        break
                    self._record_measure(point,channel,'replacement_coverage_scan')
                    self.shared_search_count+=1

    def _move_and_act(self,original_target,guard):
        target=guard.target
        estimate=getattr(target,'predicted_endpoint',None)
        if estimate is not None and target.channel not in self._pending_predictions:
            self._pending_predictions[target.channel]={'start_time_s':self.client.last_virtual_time_s,
                'start_operation_id':self._operation_id,
                'predicted_endpoint':estimate.tolist(),
                'predicted_completion_cost_s':self.open_route_planner._step_cost(
                    np.asarray(self.client.position,float),target,self.client.current_channel)}
        before=self.action_count
        reason=super()._move_and_act(original_target,guard)
        if self.action_count>before:
            self._shared_stop()
        return reason

    def _record_clear(self,point,channel,reason,**kwargs):
        if reason=='bounded_optical_probe':
            self.probe_attempts[channel]=self.probe_attempts.get(channel,0)+1
            self.channels[channel].optical_trial_count=self.probe_attempts[channel]
        super()._record_clear(point,channel,reason,**kwargs)

    def _immediate_clear_point(self,state):
        safe=state.safe_clear_point()
        if safe is None:
            return None
        safe=self._clear_point(state,safe)
        if self.planner.defer_clear_to_route and np.linalg.norm(safe-self.client.position)>20.:
            return None
        return safe

    def _plan(self,reason):
        result=super()._plan(reason)
        if self.planner.joint_service_alternatives:
            decision=next(d for d in reversed(self.diagnostics) if d['type']=='dynamic_replan')
            decision['solver']='joint_options_coordinate_descent'
        return result
