"""The tests for the Logger component."""
from collections import defaultdict
import logging
from unittest.mock import Mock, patch

import pytest

from homeassistant.components import logger
from homeassistant.components.logger import LOGSEVERITY
from homeassistant.setup import async_setup_component

HASS_NS = "unused.homeassistant"
COMPONENTS_NS = f"{HASS_NS}.components"
ZONE_NS = f"{COMPONENTS_NS}.zone"
GROUP_NS = f"{COMPONENTS_NS}.group"
CONFIGED_NS = "otherlibx"
UNCONFIG_NS = "unconfigurednamespace"


@pytest.fixture(autouse=True)
def restore_logging_class():
    """Restore logging class."""
    klass = logging.getLoggerClass()
    yield
    logging.setLoggerClass(klass)


async def test_log_filtering(hass, caplog):
    """Test logging filters."""

    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "default": "warning",
                "logs": {
                    "test.filter": "info",
                },
                "filters": {
                    "test.filter": [
                        "doesntmatchanything",
                        ".*shouldfilterall.*",
                        "^filterthis:.*",
                        "in the middle",
                    ],
                    "test.other_filter": [".*otherfilterer"],
                },
            }
        },
    )
    await hass.async_block_till_done()

    filter_logger = logging.getLogger("test.filter")

    def msg_test(logger, result, message, *args):
        logger.error(message, *args)
        formatted_message = message % args
        assert (formatted_message in caplog.text) == result
        caplog.clear()

    msg_test(
        filter_logger, False, "this line containing shouldfilterall should be filtered"
    )
    msg_test(filter_logger, True, "this line should not be filtered filterthis:")
    msg_test(filter_logger, False, "this in the middle should be filtered")
    msg_test(filter_logger, False, "filterthis: should be filtered")
    msg_test(filter_logger, False, "format string shouldfilter%s", "all")
    msg_test(filter_logger, True, "format string shouldfilter%s", "not")

    # Filtering should work even if log level is modified
    await hass.services.async_call(
        "logger",
        "set_level",
        {"test.filter": "warning"},
        blocking=True,
    )
    assert filter_logger.getEffectiveLevel() == logging.WARNING
    msg_test(
        filter_logger,
        False,
        "this line containing shouldfilterall should still be filtered",
    )

    # Filtering should be scoped to a service
    msg_test(
        filter_logger, True, "this line containing otherfilterer should not be filtered"
    )
    msg_test(
        logging.getLogger("test.other_filter"),
        False,
        "this line containing otherfilterer SHOULD be filtered",
    )


async def test_setting_level(hass):
    """Test we set log levels."""
    mocks = defaultdict(Mock)

    with patch("logging.getLogger", mocks.__getitem__):
        assert await async_setup_component(
            hass,
            "logger",
            {
                "logger": {
                    "default": "warning",
                    "logs": {
                        "test": "info",
                        "test.child": "debug",
                        "test.child.child": "warning",
                    },
                }
            },
        )
        await hass.async_block_till_done()

    assert len(mocks) == 4

    assert len(mocks[""].orig_setLevel.mock_calls) == 1
    assert mocks[""].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["WARNING"]

    assert len(mocks["test"].orig_setLevel.mock_calls) == 1
    assert mocks["test"].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["INFO"]

    assert len(mocks["test.child"].orig_setLevel.mock_calls) == 1
    assert mocks["test.child"].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["DEBUG"]

    assert len(mocks["test.child.child"].orig_setLevel.mock_calls) == 1
    assert (
        mocks["test.child.child"].orig_setLevel.mock_calls[0][1][0]
        == LOGSEVERITY["WARNING"]
    )

    # Test set default level
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger", "set_default_level", {"level": "fatal"}, blocking=True
        )
    assert len(mocks[""].orig_setLevel.mock_calls) == 2
    assert mocks[""].orig_setLevel.mock_calls[1][1][0] == LOGSEVERITY["FATAL"]

    # Test update other loggers
    with patch("logging.getLogger", mocks.__getitem__):
        await hass.services.async_call(
            "logger",
            "set_level",
            {"test.child": "info", "new_logger": "notset"},
            blocking=True,
        )
    assert len(mocks) == 5

    assert len(mocks["test.child"].orig_setLevel.mock_calls) == 2
    assert mocks["test.child"].orig_setLevel.mock_calls[1][1][0] == LOGSEVERITY["INFO"]

    assert len(mocks["new_logger"].orig_setLevel.mock_calls) == 1
    assert (
        mocks["new_logger"].orig_setLevel.mock_calls[0][1][0] == LOGSEVERITY["NOTSET"]
    )


async def test_can_set_level(hass):
    """Test logger propagation."""

    assert await async_setup_component(
        hass,
        "logger",
        {
            "logger": {
                "logs": {
                    CONFIGED_NS: "warning",
                    f"{CONFIGED_NS}.info": "info",
                    f"{CONFIGED_NS}.debug": "debug",
                    HASS_NS: "warning",
                    COMPONENTS_NS: "info",
                    ZONE_NS: "debug",
                    GROUP_NS: "info",
                },
            }
        },
    )

    assert logging.getLogger(UNCONFIG_NS).level == logging.NOTSET
    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.CRITICAL) is True
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.CRITICAL) is True
    )
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.CRITICAL)
        is True
    )

    assert logging.getLogger(CONFIGED_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(CONFIGED_NS).isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(f"{CONFIGED_NS}.any").isEnabledFor(logging.WARNING) is True
    assert (
        logging.getLogger(f"{CONFIGED_NS}.any.any").isEnabledFor(logging.WARNING)
        is True
    )
    assert logging.getLogger(f"{CONFIGED_NS}.info").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(f"{CONFIGED_NS}.info").isEnabledFor(logging.INFO) is True
    assert (
        logging.getLogger(f"{CONFIGED_NS}.info.any").isEnabledFor(logging.DEBUG)
        is False
    )
    assert (
        logging.getLogger(f"{CONFIGED_NS}.info.any").isEnabledFor(logging.INFO) is True
    )
    assert logging.getLogger(f"{CONFIGED_NS}.debug").isEnabledFor(logging.DEBUG) is True
    assert (
        logging.getLogger(f"{CONFIGED_NS}.debug.any").isEnabledFor(logging.DEBUG)
        is True
    )

    assert logging.getLogger(HASS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(HASS_NS).isEnabledFor(logging.WARNING) is True

    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.INFO) is True

    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.INFO) is True

    assert logging.getLogger(f"{GROUP_NS}.any").isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(f"{GROUP_NS}.any").isEnabledFor(logging.WARNING) is True
    assert logging.getLogger(f"{GROUP_NS}.any").isEnabledFor(logging.INFO) is True

    assert logging.getLogger(ZONE_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(f"{ZONE_NS}.any").isEnabledFor(logging.DEBUG) is True

    await hass.services.async_call(
        logger.DOMAIN, "set_level", {f"{UNCONFIG_NS}.any": "debug"}, blocking=True
    )

    assert logging.getLogger(UNCONFIG_NS).level == logging.NOTSET
    assert logging.getLogger(f"{UNCONFIG_NS}.any").level == logging.DEBUG
    assert logging.getLogger(UNCONFIG_NS).level == logging.NOTSET

    await hass.services.async_call(
        logger.DOMAIN, "set_default_level", {"level": "debug"}, blocking=True
    )

    assert logging.getLogger(UNCONFIG_NS).isEnabledFor(logging.DEBUG) is True
    assert logging.getLogger(f"{UNCONFIG_NS}.any").isEnabledFor(logging.DEBUG) is True
    assert (
        logging.getLogger(f"{UNCONFIG_NS}.any.any").isEnabledFor(logging.DEBUG) is True
    )
    assert logging.getLogger("").isEnabledFor(logging.DEBUG) is True

    assert logging.getLogger(COMPONENTS_NS).isEnabledFor(logging.DEBUG) is False
    assert logging.getLogger(GROUP_NS).isEnabledFor(logging.DEBUG) is False

    logging.getLogger(CONFIGED_NS).setLevel(logging.INFO)
    assert logging.getLogger(CONFIGED_NS).level == logging.WARNING

    logging.getLogger("").setLevel(logging.NOTSET)
