"""Prospective binary-outcome readiness, independent of retrospective significance."""
import math
import numpy as np
from scipy.optimize import brentq
from statsmodels.stats.power import NormalIndPower

def readiness(baseline_rate,available_n,treatment_fraction=.5,alpha=.05,power=.8,
              relative_lift=None,absolute_lift=None):
    if not 0<baseline_rate<1 or not 0<treatment_fraction<1 or not 0<alpha<power<1:
        raise ValueError('Require valid rate/allocation and 0 < alpha < desired power < 1')
    if (relative_lift is None)==(absolute_lift is None): raise ValueError('Specify exactly one target lift')
    delta=baseline_rate*relative_lift if absolute_lift is None else absolute_lift
    if not 0<delta<1-baseline_rate or available_n<4: raise ValueError('Invalid positive target or sample size')
    nt=int(available_n*treatment_fraction);nc=int(available_n)-nt
    if min(nt,nc)<2: raise ValueError('Each arm needs at least two participants')
    calc=NormalIndPower();ratio=(1-treatment_fraction)/treatment_fraction
    def h(d): return 2*(np.arcsin(np.sqrt(baseline_rate+d))-np.arcsin(np.sqrt(baseline_rate)))
    def achieved(d): return float(calc.power(h(d),nt,alpha=alpha,ratio=nc/nt,alternative='two-sided'))
    required_t=int(math.ceil(calc.solve_power(h(delta),alpha=alpha,power=power,ratio=ratio)))
    required_c=int(math.ceil(required_t*ratio))
    upper=1-baseline_rate-1e-10
    mde=float(brentq(lambda d:achieved(d)-power,1e-12,upper)) if achieved(upper)>=power else None
    actual=achieved(delta)
    return dict(baseline_rate=baseline_rate,target_absolute_lift=delta,treatment_fraction=treatment_fraction,
      alpha=alpha,desired_power=power,available_n=int(available_n),available_treatment_n=nt,available_control_n=nc,
      required_treatment_n=required_t,required_control_n=required_c,total_required_n=required_t+required_c,
      mde_absolute=mde,mde_relative=mde/baseline_rate if mde is not None else None,
      achieved_power=actual,readiness_status='ready' if actual>=power else 'underpowered')
