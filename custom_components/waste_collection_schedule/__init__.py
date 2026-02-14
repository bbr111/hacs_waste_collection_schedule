"""Waste Collection Schedule Component."""

from .init_ui import (
    async_migrate_entry as async_migrate_entry,
    async_setup_entry as async_setup_entry,
    async_unload_entry as async_unload_entry,
    async_update_listener as async_update_listener,
)

from .init_yaml import (
    CONFIG_SCHEMA as CONFIG_SCHEMA,
    async_setup as async_setup,
)
