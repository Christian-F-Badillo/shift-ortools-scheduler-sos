# 🕒 Shift Or-tools Scheduler (SOS) API (Optimizador de Horarios de Trabajo)

> Una API REST desarrollada en **FastAPI** y potenciada por el solver **Google OR-Tools (CP-SAT)** para automatizar la generación de horarios de personal bajo turnos rotativos, restricciones legales y permisos individuales.
>
> _Proyecto creado con dedicación para simplificar la gestión y supervisión de turnos de trabajo._

---

## 🎯 ¿Qué problema resuelve?

Coordinar los horarios semanales de equipos de trabajo suele implicar lidiar con múltiples variables complejas:

- Cubrir la demanda mínima y máxima de personal por turno y día.
- Respetar roles y áreas específicas (ej. asegurar al menos un técnico por turno).
- Gestionar ausencias, vacaciones y permisos médicos de última hora.
- Evitar prácticas indeseadas como turnos nocturnos seguidos de turnos matutinos (_clopening_).

Esta API automatiza este cálculo matemático en milisegundos utilizando Programación de Restricciones, permitiendo generar calendarios óptimos y exportarlos de forma inmediata.

---

## 🛠️ Stack Tecnológico

- **Framework Web:** [FastAPI](https://fastapi.tiangolo.com/) (Alto rendimiento y documentación automática interactiva).
- **Motor de Optimización:** [Google OR-Tools](https://developers.google.com/optimization) (`CP-SAT` Solver).
- **Base de Datos & ORM:** SQLite + [SQLAlchemy](https://www.sqlalchemy.org/) (Ligero, autocontenido y eficiente).
- **Gestión de Entorno:** `uv` / Python 3.12+.
- **Pruebas:** `pytest` & `TestClient`.

---

## 🚀 Endpoints Principales de la API

La API está estructurada en 7 módulos funcionales principales:

| Módulo             | Endpoint Base                                      | Descripción                                                                      |
| :----------------- | :------------------------------------------------- | :------------------------------------------------------------------------------- |
| **Catálogos**      | `GET /roles`, `/areas`, `/shifts`                  | Consulta los roles de empleados, áreas de trabajo y tipos de turnos disponibles. |
| **Empleados**      | `GET / POST / PATCH /employees`                    | Gestión de la plantilla de trabajo (altas, ediciones y desactivaciones).         |
| **Disponibilidad** | `PUT / DELETE /employees/{id}/availability/{date}` | Registro de vacaciones, incapacidades o días libres por empleado.                |
| **Requerimientos** | `PUT / GET /requirements/...`                      | Configuración de la demanda de personal por día, turno, rol o área.              |
| **Solver (Runs)**  | `POST /runs`                                       | **El núcleo:** Ejecuta el optimizador de OR-Tools para la semana solicitada.     |
| **Overrides**      | `PATCH /runs/{id}/assignments/{id}`                | Permite realizar cambios manuales de última hora sobre una asignación generada.  |
| **Exportación**    | `GET /runs/{id}/export?format=(csv\|xlsx)`         | Descarga el horario listo para imprimir o compartir en formato CSV o Excel.      |
| **Configuración**  | `GET / PATCH /config/constraints`                  | Ajuste de pesos y prioridades para las restricciones blandas.                    |

---

## 📦 Instalación y Ejecución Local

Asegúrate de tener instalado [uv](https://github.com/astral-sh/uv) o tu gestor de entorno preferido de Python.

1. **Clona el repositorio:**

```bash
git clone https://github.com/Christian-F-Badillo/shift-ortools-scheduler-sos.git
cd shift-craft-api
```

2. **Instala las dependencias y activa el entorno:**

```bash
uv sync
```

3. **Inicia el servidor de desarrollo:**

```bash
uv run uvicorn api:app --reload
```

4. **Explora la documentación interactiva:**

Una vez corriendo el servidor, puedes probar todos los endpoints directamente desde tu navegador en:

- Swagger UI: http://127.0.0.1:8000/docs

- ReDoc: http://127.0.0.1:8000/redoc

## 🧪 Ejecución de Pruebas

El proyecto cuenta con una suite completa de pruebas unitarias y de integración para asegurar la estabilidad del motor de optimización y las respuestas HTTP:

```bash
uv run python -m pytest -v
```

## 💡 Próximos Pasos (Frontend / Dashboard)

Construcción de una interfaz visual amigable (Dashboard web) para que la supervisión y carga de permisos se haga mediante clics en un calendario interactivo conectado a esta API.


---

## Dashboard web

La rama `feat/sos-web-dashboard` incorpora un dashboard operativo servido por FastAPI en el mismo origen que la API.

Incluye Overview, gestión de empleados, disponibilidad semanal, Schedule Builder, calendario de asignaciones, historial de ejecuciones y configuración de restricciones blandas. También permite exportar los horarios en CSV y XLSX.

### Ejecución local

```bash
uv sync
uv run uvicorn api:app --reload
```

Dashboard: http://127.0.0.1:8000/  
Swagger: http://127.0.0.1:8000/docs

### Despliegue gratuito: Render + Neon

1. Crea una base PostgreSQL gratuita en [Neon](https://neon.tech/) y copia el connection string.
2. Crea un Web Service en [Render](https://render.com/) desde este repositorio y selecciona `feat/sos-web-dashboard`.
3. Usa el build command `pip install uv && uv sync --no-dev`.
4. Usa el start command `uv run uvicorn api:app --host 0.0.0.0 --port $PORT`.
5. Configura `DATABASE_URL` con el connection string de Neon.

El archivo `render.yaml` contiene un blueprint inicial. El dashboard y la API se ejecutan en un solo servicio; PostgreSQL conserva los datos aunque el filesystem del servicio gratuito sea efímero. SQLite permanece como configuración local por defecto.

> **Seguridad:** esta versión no incluye autenticación. No la expongas con datos operativos reales hasta proteger los endpoints con autenticación y autorización.
