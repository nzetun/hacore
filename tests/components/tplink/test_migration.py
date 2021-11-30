"""Test the tplink config flow."""

from homeassistant import setup
from homeassistant.components.tplink import CONF_DISCOVERY, CONF_SWITCH, DOMAIN
from homeassistant.const import CONF_HOST, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import ALIAS, IP_ADDRESS, MAC_ADDRESS, _patch_discovery, _patch_single_discovery

from tests.common import MockConfigEntry


async def test_migration_device_online_end_to_end(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
):
    """Test migration from single config entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=ALIAS,
    )
    switch_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="switch",
        unique_id=MAC_ADDRESS,
        original_name=ALIAS,
        device_id=device.id,
    )
    light_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=dr.format_mac(MAC_ADDRESS),
        original_name=ALIAS,
        device_id=device.id,
    )
    power_sensor_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id=f"{MAC_ADDRESS}_sensor",
        original_name=ALIAS,
        device_id=device.id,
    )

    with _patch_discovery(), _patch_single_discovery():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        migrated_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                migrated_entry = entry
                break

        assert migrated_entry is not None

        assert device.config_entries == {migrated_entry.entry_id}
        assert light_entity_reg.config_entry_id == migrated_entry.entry_id
        assert switch_entity_reg.config_entry_id == migrated_entry.entry_id
        assert power_sensor_entity_reg.config_entry_id == migrated_entry.entry_id
        assert er.async_entries_for_config_entry(entity_reg, config_entry) == []

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is None


async def test_migration_device_online_end_to_end_after_downgrade(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
):
    """Test migration from single config entry can happen again after a downgrade."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    already_migrated_config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: IP_ADDRESS}, unique_id=MAC_ADDRESS
    )
    already_migrated_config_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=ALIAS,
    )
    light_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=MAC_ADDRESS,
        original_name=ALIAS,
        device_id=device.id,
    )
    power_sensor_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id=f"{MAC_ADDRESS}_sensor",
        original_name=ALIAS,
        device_id=device.id,
    )

    with _patch_discovery(), _patch_single_discovery():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert device.config_entries == {config_entry.entry_id}
        assert light_entity_reg.config_entry_id == config_entry.entry_id
        assert power_sensor_entity_reg.config_entry_id == config_entry.entry_id
        assert er.async_entries_for_config_entry(entity_reg, config_entry) == []

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is None


async def test_migration_device_online_end_to_end_ignores_other_devices(
    hass: HomeAssistant, device_reg: DeviceRegistry, entity_reg: EntityRegistry
):
    """Test migration from single config entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)

    other_domain_config_entry = MockConfigEntry(
        domain="other_domain", data={}, unique_id="other_domain"
    )
    other_domain_config_entry.add_to_hass(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MAC_ADDRESS)},
        name=ALIAS,
    )
    other_device = device_reg.async_get_or_create(
        config_entry_id=other_domain_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "556655665566")},
        name=ALIAS,
    )
    light_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="light",
        unique_id=MAC_ADDRESS,
        original_name=ALIAS,
        device_id=device.id,
    )
    power_sensor_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id=f"{MAC_ADDRESS}_sensor",
        original_name=ALIAS,
        device_id=device.id,
    )
    ignored_entity_reg = entity_reg.async_get_or_create(
        config_entry=other_domain_config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id="00:00:00:00:00:00_sensor",
        original_name=ALIAS,
        device_id=device.id,
    )
    garbage_entity_reg = entity_reg.async_get_or_create(
        config_entry=config_entry,
        platform=DOMAIN,
        domain="sensor",
        unique_id="garbage",
        original_name=ALIAS,
        device_id=other_device.id,
    )

    with _patch_discovery(), _patch_single_discovery():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        migrated_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                migrated_entry = entry
                break

        assert migrated_entry is not None

        assert device.config_entries == {migrated_entry.entry_id}
        assert light_entity_reg.config_entry_id == migrated_entry.entry_id
        assert power_sensor_entity_reg.config_entry_id == migrated_entry.entry_id
        assert ignored_entity_reg.config_entry_id == other_domain_config_entry.entry_id
        assert garbage_entity_reg.config_entry_id == config_entry.entry_id

        assert er.async_entries_for_config_entry(entity_reg, config_entry) == []

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

        legacy_entry = None
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == DOMAIN:
                legacy_entry = entry
                break

        assert legacy_entry is not None


async def test_migrate_from_yaml(hass: HomeAssistant):
    """Test migrate from yaml."""
    config = {
        DOMAIN: {
            CONF_DISCOVERY: False,
            CONF_SWITCH: [{CONF_HOST: IP_ADDRESS}],
        }
    }
    with _patch_discovery(), _patch_single_discovery():
        await setup.async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

    migrated_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == MAC_ADDRESS:
            migrated_entry = entry
            break

    assert migrated_entry is not None
    assert migrated_entry.data[CONF_HOST] == IP_ADDRESS


async def test_migrate_from_legacy_entry(hass: HomeAssistant):
    """Test migrate from legacy entry that was already imported from yaml."""
    data = {
        CONF_DISCOVERY: False,
        CONF_SWITCH: [{CONF_HOST: IP_ADDRESS}],
    }
    config_entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=DOMAIN)
    config_entry.add_to_hass(hass)
    with _patch_discovery(), _patch_single_discovery():
        await setup.async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    migrated_entry = None
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == MAC_ADDRESS:
            migrated_entry = entry
            break

    assert migrated_entry is not None
    assert migrated_entry.data[CONF_HOST] == IP_ADDRESS
