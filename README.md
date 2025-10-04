# Onto3D

*A Blender add-on to model, visualize, and link CIDOC-CRM–inspired semantic graphs (with RDF/OWL import) directly in the Node Editor.*

> **Short description:** Onto3D lets you import ontologies (TTL/RDF/XML/OWL), create “Entity/Property” nodes aligned with CIDOC-CRM and extensions, and link entities to scene geometry for digital archaeology and heritage workflows.

<!-- Optional screenshot -->
<!-- ![Onto3D in the Node Editor](docs/screenshot-node-editor.png) -->

---

## Features

- **Node-based modeling:** “Entity” and “Property” nodes inspired by CIDOC-CRM (E- and P- codes; extensible to CRMarchaeo, CRMsci, CRMBa, etc.).
- **Ontology import:** Load TTL / RDF/XML / OWL (via `rdflib`), map classes and properties, and auto-generate presets for the Add menu.
- **Open IRI:** Button on nodes and in the N-Panel “Item” area to open the selected resource IRI in the system browser.
- **Connect Geometry:** Link one or more scene objects (including groups under an Empty) to a selected entity node.
- **N-Panel “Onto3D”:** Panels for ontology import & presets, geometry connections, and utilities.
- **Namespace-aware:** Handle multiple namespaces (CRM, CRMarchaeo, CRMsci, CRMBa…).
- **Semantic versioning:** Clear changelog and versioning (SemVer).

> **Roadmap (short):** TTL/OWL graph export; individual import from JSON-LD (if `rdflib-jsonld` is available); extended docs and examples.

---

## Requirements

- **Blender** ≥ 4.5 LTS  
- **Python** (bundled with Blender)  
- **rdflib** (recommended for ontology import). If missing, the add-on will attempt lazy import and guide installation.

---

## Installation

1. Download the latest **release ZIP** (the ZIP of the `addon/` folder).
2. In Blender: **Edit → Preferences → Add-ons → Install…**
3. Select the ZIP and enable **Onto3D**.
4. Open the **Node Editor** and the **N-Panel → Onto3D** tab.

---

## Quick Start

1. **Import an ontology:** N-Panel → *Import Ontologies* → select TTL / RDF/XML / OWL.  
2. **Generate presets:** Click *Generate Presets* to populate the Add menu with classes and properties.  
3. **Add nodes:** **Add → CRM/CRA/…** → choose an **Entity** (e.g., `E22 Man-Made Object`) and connect **Property** nodes (e.g., `P46 is composed of`).  
4. **Open IRI:** On the node or in the Item panel, use **Open IRI in Browser** to view the authoritative definition.  
5. **Link geometry:** N-Panel → *Connect Geometry* → **Create Connection** (select an entity node, then one or more scene objects/Empties). Use **Break Connection** to detach.

---

## Panels & Operators (overview)

- **Import Ontologies**
  - *Import* (TTL/RDF/XML/OWL)
  - *Reload* / *Clear Presets* / *Generate Presets*
- **Connect Geometry**
  - *Create Connection* (supports multi-selection and Empties as containers)
  - *Break Connection*
  - Read-only list of scene objects linked to the active entity node
- **Item / Node Tools**
  - *Open IRI in Browser* (on node and in the Item panel)

---

## File Formats & Notes

- **Tested:** TTL, RDF/XML, OWL via `rdflib`.
- **JSON-LD:** Possible when `rdflib-jsonld` is present in the Blender Python environment (not guaranteed by default).
- **Labels vs codes:** Class/property labels and prefixes depend on the ontology’s namespaces/labels; the add-on displays *prefix + label* where available.

---

## Project Structure (repository)

# Onto3D

*A Blender add-on to model, visualize, and link CIDOC-CRM–inspired semantic graphs (with RDF/OWL import) directly in the Node Editor.*

> **Short description:** Onto3D lets you import ontologies (TTL/RDF/XML/OWL), create “Entity/Property” nodes aligned with CIDOC-CRM and extensions, and link entities to scene geometry for digital archaeology and heritage workflows.

<!-- Optional screenshot -->
<!-- ![Onto3D in the Node Editor](docs/screenshot-node-editor.png) -->

---

## Features

- **Node-based modeling:** “Entity” and “Property” nodes inspired by CIDOC-CRM (E- and P- codes; extensible to CRMarchaeo, CRMsci, CRMBa, etc.).
- **Ontology import:** Load TTL / RDF/XML / OWL (via `rdflib`), map classes and properties, and auto-generate presets for the Add menu.
- **Open IRI:** Button on nodes and in the N-Panel “Item” area to open the selected resource IRI in the system browser.
- **Connect Geometry:** Link one or more scene objects (including groups under an Empty) to a selected entity node.
- **N-Panel “Onto3D”:** Panels for ontology import & presets, geometry connections, and utilities.
- **Namespace-aware:** Handle multiple namespaces (CRM, CRMarchaeo, CRMsci, CRMBa…).
- **Semantic versioning:** Clear changelog and versioning (SemVer).

> **Roadmap (short):** TTL/OWL graph export; individual import from JSON-LD (if `rdflib-jsonld` is available); extended docs and examples.

---

## Requirements

- **Blender** ≥ 4.5 LTS  
- **Python** (bundled with Blender)  
- **rdflib** (recommended for ontology import). If missing, the add-on will attempt lazy import and guide installation.

---

## Installation

1. Download the latest **release ZIP** (the ZIP of the `addon/` folder).
2. In Blender: **Edit → Preferences → Add-ons → Install…**
3. Select the ZIP and enable **Onto3D**.
4. Open the **Node Editor** and the **N-Panel → Onto3D** tab.

---

## Quick Start

1. **Import an ontology:** N-Panel → *Import Ontologies* → select TTL / RDF/XML / OWL.  
2. **Generate presets:** Click *Generate Presets* to populate the Add menu with classes and properties.  
3. **Add nodes:** **Add → CRM/CRA/…** → choose an **Entity** (e.g., `E22 Man-Made Object`) and connect **Property** nodes (e.g., `P46 is composed of`).  
4. **Open IRI:** On the node or in the Item panel, use **Open IRI in Browser** to view the authoritative definition.  
5. **Link geometry:** N-Panel → *Connect Geometry* → **Create Connection** (select an entity node, then one or more scene objects/Empties). Use **Break Connection** to detach.

---

## Panels & Operators (overview)

- **Import Ontologies**
  - *Import* (TTL/RDF/XML/OWL)
  - *Reload* / *Clear Presets* / *Generate Presets*
- **Connect Geometry**
  - *Create Connection* (supports multi-selection and Empties as containers)
  - *Break Connection*
  - Read-only list of scene objects linked to the active entity node
- **Item / Node Tools**
  - *Open IRI in Browser* (on node and in the Item panel)

---

## File Formats & Notes

- **Tested:** TTL, RDF/XML, OWL via `rdflib`.
- **JSON-LD:** Possible when `rdflib-jsonld` is present in the Blender Python environment (not guaranteed by default).
- **Labels vs codes:** Class/property labels and prefixes depend on the ontology’s namespaces/labels; the add-on displays *prefix + label* where available.

---

## Project Structure (repository)
-Onto3D/
  ├─ addon/ # installable add-on (zip this folder level)
  │ ├─ init.py # bl_info, register/unregister, bootstrap
  │ ├─ ui.py # UI panels (N-Panel, menus)
  │ ├─ operators.py # operators (import, presets, connections, utils)
  │ ├─ nodes/ # custom node definitions (entity/property)
  │ ├─ utils/ # helpers (RDF parsing, mappings, etc.)
  │ └─ icons/ # (optional)
  ├─ docs/ # screenshots/GIFs/docs (optional)
  ├─ examples/ # small sample files (optional)
  ├─ CHANGELOG.md
  ├─ LICENSE
  └─ README.md

> Distribute the add-on by zipping the **contents of `addon/`** and installing that ZIP in Blender.

---

## Versioning

Onto3D follows **Semantic Versioning**: `MAJOR.MINOR.PATCH` (e.g., `0.5.0`).  
The version is defined in `addon/__init__.py` under `bl_info["version"]`.

---

## Troubleshooting

- **`rdflib` not found:** Install `rdflib` into Blender’s Python (or an accessible environment), then restart Blender.  
- **Empty presets after import:** Ensure the ontology exposes classes/properties with recognizable namespaces; run *Generate Presets* again.  
- **Missing E/P prefixes:** Depends on how the ontology provides labels/prefixes; check namespace mappings.  
- **Large ontologies feel slow:** This can be normal with very large TTL/OWL. Consider filtering or splitting.

---

## Contributing

Bug reports and pull requests are welcome. Please:
- Keep one feature/fix per PR with a clear description.
- Follow the existing code style and module layout.
- Update `CHANGELOG.md` and docs where relevant.

---

## License

**MIT License** — see `LICENSE`.

---

## Citation

If you use Onto3D in scholarly work, please cite this repository (a `CITATION.cff` file may be added later). Example:

> Onto3D — Blender add-on for CIDOC-CRM-like semantic graph modeling and RDF/OWL import. CNR ISPC & contributors. Version: _[insert version]_.

---

## Acknowledgments

Developed for and with the **digital archaeology** and **heritage science** communities.  
Thanks to Blender and the open-source ecosystem.
