VERSION = '1.2.0'

DOMAIN = 'light_store'

ATTR_OPERATION  = 'operation'
ATTR_OP_SAVE    = 'save'
ATTR_OP_RESTORE = 'restore'
ATTR_OVERWRITE  = 'overwrite'

ATTR_STORE_NAME = 'store_name'
ATTR_ENTITY_ID  = 'entity_id'

# Select light attributes to save/restore.
ATTR_BRIGHTNESS = "brightness"
ATTR_EFFECT = "effect"
ATTR_WHITE_VALUE = "white_value"
ATTR_COLOR_TEMP = "color_temp"
ATTR_HS_COLOR = "hs_color"
# Save any of these attributes.
GEN_ATTRS = [ATTR_BRIGHTNESS, ATTR_EFFECT]
# Save only one of these attributes, in order of precedence.
COLOR_ATTRS = [ATTR_WHITE_VALUE, ATTR_COLOR_TEMP, ATTR_HS_COLOR]

def store_entity_id(store_name, entity_id):
    return '{}.{}'.format(store_name, entity_id.replace('.', '_'))

# Get operation (default to save.)
operation = data.get(ATTR_OPERATION, ATTR_OP_SAVE)
if operation not in [ATTR_OP_SAVE, ATTR_OP_RESTORE]:
    logger.error('Invalid operation. Expected {} or {}, got: {}'.format(
        ATTR_OP_SAVE, ATTR_OP_RESTORE, operation))
else:
    # Get optional store name (default to DOMAIN.)
    store_name = data.get(ATTR_STORE_NAME, DOMAIN)
    
    # Get optional overwrite parameter (only applies to saving.)
    overwrite = data.get(ATTR_OVERWRITE, True)

    # Get optional list (or comma separated string) of switches & lights to
    # save/restore.
    entity_id = data.get(ATTR_ENTITY_ID)
    if isinstance(entity_id, str):
        entity_id = [e.strip() for e in entity_id.split(',')]

    # Replace any group entities with their contents.
    # Repeat until no groups left in list.
    expanded_a_group = True
    while entity_id and expanded_a_group:
        expanded_a_group = False
        for e in entity_id:
            if e.startswith('group.'):
                entity_id.remove(e)
                g = hass.states.get(e)
                if g and 'entity_id' in g.attributes:
                    entity_id.extend(g.attributes['entity_id'])
                    expanded_a_group = True

    # Get lists of switches and lights that actually exist,
    # and list of entities that were previously saved.
    entity_ids = (hass.states.entity_ids('switch') +
                  hass.states.entity_ids('light'))
    saved      = hass.states.entity_ids(store_name)
    # When restoring, limit to existing entities that were saved.
    if operation == ATTR_OP_RESTORE:
        saved_entity_ids = []
        for e in entity_ids:
            if store_entity_id(store_name, e) in saved:
                saved_entity_ids.append(e)
        entity_ids = saved_entity_ids

    # If a list of entities was specified, further limit to just those.
    # Otherwise, save all existing switches and lights, or restore
    # all existing switches and lights that were previously saved.
    if entity_id:
        entity_ids = tuple(set(entity_ids).intersection(set(entity_id)))

    if operation == ATTR_OP_SAVE:
        # Only save if not already saved, or if overwite is True.
        if not saved or overwrite:
            # Clear out any previously saved states.
            for entity_id in saved:
                hass.states.remove(entity_id)

            # Save selected switches and lights to store.
            for entity_id in entity_ids:
                cur_state = hass.states.get(entity_id)
                if cur_state is None:
                    logger.error('Could not get state of {}.'.format(entity_id))
                else:
                    attributes = {}
                    if entity_id.startswith('light.') and cur_state.state == 'on':
                        for attr in GEN_ATTRS:
                            if attr in cur_state.attributes:
                                attributes[attr] = cur_state.attributes[attr]
                        for attr in COLOR_ATTRS:
                            if attr in cur_state.attributes:
                                attributes[attr] = cur_state.attributes[attr]
                                break
                    hass.states.set(store_entity_id(store_name, entity_id),
                                    cur_state.state, attributes)
    else:
        # Restore selected switches and lights from store.
        for entity_id in entity_ids:
            old_state = hass.states.get(store_entity_id(store_name, entity_id))
            if old_state is None:
                logger.error('No saved state for {}.'.format(entity_id))
            else:
                turn_on = old_state.state == 'on'
                service_data = {'entity_id': entity_id}
                component = entity_id.split('.')[0]
                if component == 'light' and turn_on and old_state.attributes:
                    service_data.update(old_state.attributes)
                hass.services.call(component,
                                   'turn_on' if turn_on else 'turn_off',
                                   service_data)

        # Remove saved states now that we're done with them.
        for entity_id in saved:
            hass.states.remove(entity_id)