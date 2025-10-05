# Onto3D – CIDOC-like Graph Editor for Blender

**Version 0.5**

Onto3D is a Blender add-on designed to create, visualize, and manage semantic networks based on the **CIDOC-CRM** and related ontologies (CRMarchaeo, CRMsci, etc.).  
It allows researchers to model archaeological and heritage data directly inside Blender’s node editor, linking entities, properties, and geometries in a unified visual graph.

---

## ✨ Key Features

- **Ontology Importer**  
  Load and parse ontology files in RDF/TTL/OWL format directly into Blender.  
  Automatically generate entity and property nodes based on ontology classes and predicates.

- **CIDOC Graph Nodes**  
  Create, connect, and visualize CIDOC-like entities (e.g. *E22 Man-Made Object*, *A1 Excavation Process Unit*, *S4 Observation*).  
  Each node stores metadata such as labels, descriptions, and IRIs.

- **Semantic Property Nodes**  
  Add and connect relationships (*P46 is composed of*, *P131 is identified by*, etc.) between entities.

- **Geometry Connection Panel**  
  Link Blender objects (meshes, empties, collections) to ontology nodes via the **Connect Geometry** tools.  
  Support for multiple geometry associations and easy disconnection.

- **Entity Information Panel (N-Panel)**  
  Edit node metadata directly from the side panel: title, description, IRI (with quick-open browser button).  
  Includes tools to isolate or frame selected entities in the 3D View.

- **RDF Export (work-in-progress)**  
  Planned support for exporting the graph as RDF/Turtle or JSON-LD.

---

## 🧩 Installation

1. Download the latest release ZIP from  
   👉 [https://github.com/gmancuso24/Onto3D/releases](https://github.com/gmancuso24/Onto3D/releases)

2. In Blender:  
   - Open **Edit → Preferences → Add-ons**  
   - Click **Install…** and select the `onto3d-0.5.zip` file  
   - Enable the add-on **Onto3D – CIDOC Graph Editor**

3. A new editor type **Onto3D Graph** and an **Onto3D** tab will appear in the N-Panel.

---

## 🚀 Quick Start

1. Open a **new Onto3D Graph** editor window.  
2. Go to **Edit → Preferences → Add-ons → Onto3D → Settings Panel**, and use **Import Ontology** to load a CIDOC-CRM or compatible ontology (TTL/OWL).  
   - Ontologies imported here will populate the available entity and property types within the graph.  
3. Create entity and property nodes from the sidebar or via the **Add** menu.  
4. Use the **Connect Geometry** panel (in the N-Panel) to bind nodes to selected 3D objects.  
5. Save your `.blend` file — all semantic links remain embedded in the scene.

---

## 📁 Repository Structure
onto3d/
  ├── init.py # Main add-on registration
  ├── ui_panels.py # N-Panel interface and geometry tools
  ├── nodes_entities.py # Entity node definitions
  ├── nodes_properties.py # Property node definitions
  ├── ontology_importer.py # RDF/TTL import utilities
  ├── icons/ # Add-on icons and assets
  └── README.md # This file

---

## 🧠 Requirements

- **Blender 4.0+**  
- **Python 3.11+** (included with Blender)
- **rdflib** Python package (auto-import or install manually via `pip install rdflib`)

---

## 🧑‍💻 Maintainers

- **Giacomo Mancuso** — CNR ISPC, Rome  
- **ChatGPT (GPT-5)** — code design and workflow automation support

---

## 🪐 License

This project is released under the **MIT License**.  
You are free to use, modify, and redistribute the code with appropriate attribution.

---

## 🧭 Acknowledgements

Onto3D was developed within the framework of research on **semantic modeling and Linked Open Data** for archaeology and heritage science.  
It draws inspiration from the **CIDOC-CRM** ontology and its archaeological extensions.

> *“Linking archaeological knowledge to its spatial and semantic dimensions.”*
