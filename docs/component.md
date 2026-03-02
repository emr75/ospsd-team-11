# Component Definition

Every workspace component lives under `components/<component_name>/`. Each component is either:

- a contract (implementation-independent interface)
- a concrete implementation of a contract (e.g., Google Calendar).

Components are designed to be wired together via dependency injection (DI) so the rest of the codebase depends only on contracts.


## Directory Layout

Each component follows this structure:

```text
components/<component_name>/
├── pyproject.toml
├── README.md
├── src/<component_name>/
│   ├── __init__.py
│   ├── client.py     # contracts / public types live here (if applicable)
│   ├── event.py      # shared event contract/types (if applicable)
│   ├── registry.py   # DI registry (if applicable)
│   ├── client_impl.py# concrete implementations live here (for impl components only)
│   └── event_impl.py # concrete implementations live here (for impl components only)
└── tests/            # optional component-scoped tests
```

## pyproject.toml Checklist
- `[project]`: align `name` with the folder, set `version`, `description`, `readme = "README.md"`, `requires-python = ">=3.13"`, and list direct dependencies.
- `[build-system]`: keep hatchling as the backend.
- `[tool.uv.sources]`: declare workspace dependencies when another component is required.

## README Expectations
Document, at minimum: component’s role, scope, factory functions (if any), and component dependencies. Keep examples using absolute imports.

## Implementation Notes (_impl.py)

Place concrete classes here so `__init__.py` can focus on exports and dependency injection wiring.

## Package Initialisation (\_\_init\_\_.py)
- Contract packages: define the ABC and get_* factory that raises NotImplementedError.
- Implementation packages: import the contract, handle provider-specific authentication and configuration,
register themselves with the contract’s DI registry on import.

## Testing

Component-level tests belong in tests/. Target the public interface, use mocks to isolate external services, and keep fixtures local to the component.