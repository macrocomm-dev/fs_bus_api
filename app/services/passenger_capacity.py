"""Fleet-series capacity rules shared by capture and dashboard reporting."""
import re

CAPACITIES = {3: (65, 12), 4: (114, 32), 5: (79, 24), 7: (49, 12)}


def vehicle_capacity(fleet_number):
    value = str(fleet_number or '').strip()
    if not re.fullmatch(r'[3457][0-9]{3}', value):
        return None, None
    return CAPACITIES[int(value[0])]


def passenger_assessment(fleet_number, seated, standing):
    seating_capacity, standing_capacity = vehicle_capacity(fleet_number)
    known = seating_capacity is not None and seated is not None and standing is not None
    excess = (max(seated - seating_capacity, 0) + max(standing - standing_capacity, 0)) if known else None
    return {
        'seating_capacity': seating_capacity,
        'standing_capacity': standing_capacity,
        'overloaded_passengers': excess,
        'pass_': excess == 0 if known else None,
    }


def inspection_pass(inspection):
    if inspection.inspection_type == 'count':
        return passenger_assessment(inspection.fleet_number, inspection.number_seated, inspection.number_standing)['pass_']
    return inspection.pass_


def passenger_violation_sql(alias=''):
    """PostgreSQL expression equivalent to passenger_assessment; unknown is NULL.

    Alias is a developer-supplied table qualifier, never user input.
    """
    prefix = alias + '.' if alias else ''
    fleet = f'btrim({prefix}fleet_number)'
    seat = 'CASE ' + ' '.join(f"WHEN {fleet} ~ '^{series}[0-9]{{3}}$' THEN {limits[0]}" for series, limits in CAPACITIES.items()) + ' END'
    stand = 'CASE ' + ' '.join(f"WHEN {fleet} ~ '^{series}[0-9]{{3}}$' THEN {limits[1]}" for series, limits in CAPACITIES.items()) + ' END'
    return f'(CASE WHEN {prefix}number_seated IS NOT NULL AND {prefix}number_standing IS NOT NULL THEN ({prefix}number_seated > ({seat}) OR {prefix}number_standing > ({stand})) END)'


def inspection_violation_expression(model):
    from sqlalchemy import case, literal_column
    return case(
        (model.inspection_type == 'count', literal_column(passenger_violation_sql('inspections.inspections'))),
        else_=model.pass_.is_(False),
    )
