"""Monitoring contract for actual future event exports; never invent arrival data."""
import pandas as pd

def event_health(events, expected_event_ids=None, allowed_lateness_hours=24):
    """Expected IDs must come from an authoritative, completed source manifest.

    Missing events cannot be inferred from yesterday's volume alone. Received time
    must be source-system arrival time, not the time this historical file downloaded.
    """
    if allowed_lateness_hours < 0: raise ValueError('Lateness tolerance must be nonnegative')
    if 'event_id' not in events: raise ValueError('event_id required')
    duplicates=int(events.event_id.duplicated().sum())
    result={'rows':len(events),'duplicate_event_ids':duplicates,
            'missing_events':None,'missing_event_rate':None,
            'late_events':None,'late_event_rate':None,'invalid_timestamps':None}
    if expected_event_ids is not None:
        expected=set(expected_event_ids)
        missing=expected-set(events.event_id.dropna())
        result.update(missing_events=len(missing),missing_event_rate=len(missing)/len(expected) if expected else None)
    required={'event_timestamp_utc','received_timestamp_utc'}
    if required.issubset(events.columns):
        event_time=pd.to_datetime(events.event_timestamp_utc,utc=True,errors='coerce')
        received=pd.to_datetime(events.received_timestamp_utc,utc=True,errors='coerce')
        valid=event_time.notna()&received.notna()
        lag=(received-event_time).dt.total_seconds()/3600
        invalid=(~valid)|(lag<0)
        valid &= ~invalid
        result['invalid_timestamps']=int(invalid.sum())
        if valid.any():
            late=int((lag[valid]>allowed_lateness_hours).sum())
            result.update(late_events=late,late_event_rate=late/int(valid.sum()))
    return result
