# 🕒 Shift Or-tools Scheduler (SOS) API (Optimizador de Horarios de Trabajo)

> Una API REST desarrollada en **FastAPI** y potenciada por **Google OR-Tools (CP-SAT)** para automatizar la generación de horarios de personal bajo turnos rotativos, restricciones legales y permisos individuales.

## ¿Qué problema resuelve?

Coordinar los horarios semanales de equipos de trabajo implica cubrir la demanda mínima y máxima por turno, respetar roles y áreas, gestionar ausencias y evitar combinaciones indeseadas de turnos. SOS automatiza este cálculo mediante programación de restricciones y permite consultar y exportar los calendarios generados.

## Stack tecnológico

- **API y servidor:** FastAPI + Uvicorn.
- **Optimización:** Google OR-Tools (CP-SAT).
- **Persistencia:** SQLite + SQLAlchemy.
- **Frontend:** dashboard web servido por FastAPI.
- **Entorno:** uv / Python 3.12+.
- **Pruebas:** pytest + TestClient.

## Endpoints principales

| Módulo | Endpoint base | Descripción |
| :--- | :--- | :--- |
| Catálogos | `GET /roles`, `/areas`, `/shifts` | Roles, áreas y turnos. |
| Empleados | `/employees` | Altas, consultas y actualizaciones de empleados. |
| Disponibilidad | `/employees/{id}/availability` | Consulta y edición de disponibilidad por fecha. |
| Requerimientos | `/requirements` | Demanda de personal por semana, turno, rol y área. |
| Solver | `POST /runs` | Ejecuta el optimizador para una semana. |
| Asignaciones | `/runs/{id}/assignments` | Consulta y modifica asignaciones generadas. |
| Exportación | `/runs/{id}/export?format=csv|xlsx` | Descarga horarios en CSV o Excel. |
| Configuración | `/config/constraints` | Consulta y ajusta restricciones blandas. |

## Instalación y ejecución local

Requiere Python 3.12+ y [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Christian-F-Badillo/shift-ortools-scheduler-sos.git
cd shift-ortools-scheduler-sos
uv sync
uv run uvicorn api:app --reload
```

- Dashboard: http://127.0.0.1:8000/
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

SQLite crea `scheduler.db` en el directorio de trabajo de forma predeterminada. Para cambiar su ubicación:

```bash
SQLITE_PATH=/ruta/absoluta/scheduler.db uv run uvicorn api:app --reload
```

## Catálogos de roles y departamentos

Antes de registrar empleados, crea al menos un rol. Desde la sección **Roles & departments** del dashboard puedes crear roles y departamentos/áreas. También están disponibles estos endpoints:

- `GET /roles` y `POST /roles` con cuerpo `{"name":"Supervisor"}`.
- `GET /areas` y `POST /areas` con cuerpo `{"name":"Operaciones"}`.

El departamento es opcional al crear un empleado; el rol es obligatorio. Los nombres duplicados se rechazan con HTTP 409.

## Dashboard web

La rama `feat/sos-web-dashboard` incorpora un dashboard responsive servido desde el mismo origen que la API. Incluye overview, gestión de empleados y catálogos de roles/departamentos, disponibilidad semanal, generación de horarios, calendario de asignaciones, historial de ejecuciones y configuración de restricciones blandas.

## Despliegue en Render

El archivo `render.yaml` configura un Web Service con el plan de cómputo pagado más pequeño disponible (`0.5c-512mb`) y un Persistent Disk de 1 GB montado en `/var/data`. La variable `SQLITE_PATH=/var/data/scheduler.db` hace que la base se escriba dentro del volumen persistente.

1. Crea un Blueprint en [Render](https://render.com/) desde este repositorio y selecciona la rama `feat/sos-web-dashboard`.
2. Revisa el plan del servicio y el disco persistente antes de confirmar la creación.
3. Render instalará dependencias con `uv sync --no-dev` e iniciará FastAPI.
4. Al terminar el despliegue, abre la URL del servicio; el dashboard está en `/` y Swagger en `/docs`.

**Importante sobre costos y persistencia:** Render no permite adjuntar Persistent Disks a servicios gratuitos. El plan configurado en el Blueprint es `0.5c-512mb` (plan de pago) porque SQLite necesita almacenamiento persistente para conservar los datos entre reinicios y despliegues. Un servicio Free puede servir para una demostración, pero su filesystem es efímero y no debe usarse como almacenamiento de la base de datos.

Consulta la documentación oficial de [Persistent Disks](https://render.com/docs/disks) y [Blueprints](https://render.com/docs/blueprint-spec) para conocer límites y precios vigentes.

## Seguridad

El dashboard y los endpoints de la API todavía no implementan autenticación ni autorización. No despliegues esta versión con datos reales de empleados ni la expongas como servicio operativo hasta añadir autenticación, autorización y protección de todas las rutas de datos. Servir el dashboard y la API desde el mismo origen no sustituye esos controles.

## Pruebas

```bash
uv run pytest -v
```
