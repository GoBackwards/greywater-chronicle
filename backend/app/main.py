import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel, ConfigDict, Field

from app.chronicle.models import (
    MillStatus,
    RepairMill,
)
from app.chronicle.service import (
    IdempotencyConflict,
    RevisionConflict,
    execute_repair_mill,
)
from app.chronicle.reducer import replay
from app.chronicle.handlers import CommandRejected
from app.chronicle.store import load_events
from app.database import (
    get_database_connection,
    initialize_database,
)
from app.session_store import (
    PlayerSession,
    append_player_session,
    load_player_session,
)

from secrets import token_urlsafe
from uuid import uuid4

NPC_DIALOGUE = {
    "guard": {
        "name": "Guard",
        "dialogue": "Welcome to Greywater. State your business, traveler.",
    },
    "miller": {
        "name": "Miller",
        "dialogue": "Mill wheel snapped last Sabbath. No flour till it's mended, and the wright's overbooked. Sorry, friend.",
    },
    "reeve": {
        "name": "Reeve",
        "dialogue": "Half the village at my door with complaints, and the crown's tax rolls due by month's end. If you've a grievance, form a queue.",
    },
}

MILLER_DIALOGUE_BY_STATUS = {
    MillStatus.BROKEN: (
        "Mill wheel snapped last Sabbath. "
        "No flour till it's mended, and the "
        "wright's overbooked. Sorry, friend."
    ),
    MillStatus.WORKING: (
        "The mill wheel is turning again. "
        "Greywater has flour once more."
    ),
}

DEFAULT_DATABASE_PATH = (
    Path(__file__).parents[1] / "chronicle.db"
)

bearer_scheme = HTTPBearer(auto_error=False)

class WorldResponse(BaseModel):
    revision: int
    mill_status: MillStatus

class SessionResponse(BaseModel):
    player_id: str
    session_token: str

class RepairMillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(
        min_length=1,
        max_length=128,
    )
    expected_revision: int = Field(ge=0)


class RepairMillResponse(BaseModel):
    revision: int
    event_type: Literal["mill_repaired"]
    actor_id: str

def create_app(
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        initialize_database(database_path)
        yield


    application = FastAPI(lifespan=lifespan)
    application.state.database_path = database_path

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Demo only; restrict before production.
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @application.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "chronicle-backend",
        }

    @application.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    )
    def create_session(
        connection: Annotated[
            sqlite3.Connection,
            Depends(get_database_connection),
        ],
    ) -> SessionResponse:
        session = PlayerSession(
            player_id=f"player-{uuid4()}",
            session_token=token_urlsafe(32),
        )

        try:
            append_player_session(
                connection=connection,
                session=session,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

        return SessionResponse(
            player_id=session.player_id,
            session_token=session.session_token,
        )

    @application.post(
    "/commands/repair-mill",
    response_model=RepairMillResponse,
    )
    def repair_mill(
        payload: RepairMillRequest,
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer_scheme),
        ],
        connection: Annotated[
            sqlite3.Connection,
            Depends(get_database_connection),
        ],
    ) -> RepairMillResponse:
        if credentials is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_session"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        session = load_player_session(
            connection=connection,
            session_token=credentials.credentials,
        )

        if session is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_session"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            result = execute_repair_mill(
                connection=connection,
                command_id=payload.command_id,
                command=RepairMill(),
                actor_id=session.player_id,
                expected_revision=payload.expected_revision,
            )
        except RevisionConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "world_revision_conflict",
                    "expected_revision": exc.expected_revision,
                    "actual_revision": exc.actual_revision,
                },
            ) from exc

        except CommandRejected as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": str(exc),
                },
            ) from exc

        except IdempotencyConflict as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "idempotency_key_reused",
                    "command_id": exc.command_id,
                },
            ) from exc

        return RepairMillResponse(
            revision=result.revision,
            event_type="mill_repaired",
            actor_id=result.event.actor_id,
        )

    @application.get("/world", response_model=WorldResponse,)
    def get_world(
        connection: Annotated[
            sqlite3.Connection,
            Depends(get_database_connection),
        ],
    ) -> WorldResponse:
        stored_events = load_events(connection)

        state = replay(
            [
                stored_event.event
                for stored_event in stored_events
            ]
        )

        revision = (
            stored_events[-1].revision
            if stored_events
            else 0
        )

        return WorldResponse(
            revision=revision,
            mill_status=state.mill_status,
        )

    @application.get("/npcs/{npc_id}/dialogue")
    def get_npc_dialogue(
        npc_id: str,
        connection: Annotated[
            sqlite3.Connection,
            Depends(get_database_connection),
        ],
    ):
        normalized_npc_id = npc_id.lower()
        entry = NPC_DIALOGUE.get(normalized_npc_id)

        if not entry:
            raise HTTPException(
                status_code=404,
                detail=f"NPC '{npc_id}' not found",
            )

        dialogue = entry["dialogue"]

        if normalized_npc_id == "miller":
            stored_events = load_events(connection)

            state = replay(
                [
                    stored_event.event
                    for stored_event in stored_events
                ]
            )

            dialogue = MILLER_DIALOGUE_BY_STATUS[
                state.mill_status
            ]

        return {
            "npc_id": normalized_npc_id,
            "name": entry["name"],
            "dialogue": dialogue,
        }

    return application


app = create_app()