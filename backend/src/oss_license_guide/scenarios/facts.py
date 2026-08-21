"""Scenario fact types and their provenance.

Facts describe the use scenario. Provenance distinguishes facts the user
stated explicitly, facts derived deterministically, and facts that are unknown.
Unknown facts never receive a favorable default.
"""

from __future__ import annotations

from enum import StrEnum


class FactType(StrEnum):
    """The kinds of material facts that describe a scenario."""

    EXPRESSION = "expression"
    ACTION = "action"
    DISTRIBUTION = "distribution"
    DISTRIBUTION_FORM = "distribution_form"
    RECIPIENT = "recipient"
    MODIFIED = "modified"
    OUTBOUND_LICENSE = "outbound_license"
    SELECTED_BRANCH = "selected_branch"


class Provenance(StrEnum):
    """Where a fact value came from."""

    USER_PROVIDED = "user_provided"
    DERIVED = "derived"
    UNKNOWN = "unknown"


class Action(StrEnum):
    """The intended action against the licensed component."""

    USE = "use"
    MODIFY = "modify"
    COPY = "copy"
    LINK = "link"
    AGGREGATE = "aggregate"
    REDISTRIBUTE = "redistribute"
    SUBLICENSE = "sublicense"


class DistributionForm(StrEnum):
    """The form in which the component is distributed, if at all."""

    NONE = "none"
    SOURCE = "source"
    BINARY = "binary"
    CONTAINER = "container"
    NETWORK_SERVICE = "network_service"
    CLIENT_SIDE = "client_side"


class Recipient(StrEnum):
    """Who receives the distributed component."""

    EMPLOYEES = "employees"
    CONTRACTORS = "contractors"
    CUSTOMERS = "customers"
    PUBLIC = "public"
