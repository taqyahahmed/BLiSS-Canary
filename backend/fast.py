import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request

from backend.config import (APP_NAME, WEBSOCKET_URL,WEBSOCKET_RECONNECT_DELAY,WEBSOCKET_TIMEOUT)
from backend.database import create_client
from backend.main import CanaryPipeline
from backend.websocket_client import WebSocketClient


logger = logging.getLogger(__name__)

SensorName = Literal[
    "ecg",
    "ppg",
    "bioimpedance",
    "imu",
    "temperature",
]

#startup/shutdown

@asynccontextmanager
async def lifespan(app: FastAPI):
    database_client = create_client()
    listener_task = None

    try:
        pipeline = CanaryPipeline(
            database_client=database_client,
        )

        hardware_client = WebSocketClient(
            url=WEBSOCKET_URL,
            reconnect_delay=WEBSOCKET_RECONNECT_DELAY,
            connection_timeout=WEBSOCKET_TIMEOUT,
        )

        app.state.pipeline = pipeline
        app.state.hardware_client = hardware_client

        listener_task = asyncio.create_task(
            hardware_client.run(pipeline.handle_message)
        )

        app.state.listener_task = listener_task

        yield

    finally:
        try:
            if listener_task is not None:
                listener_task.cancel()

                try:
                    await listener_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception(
                        "hardware listener stopped due to error"
                    )
        finally:
            database_client.close()


app = FastAPI(
    title=APP_NAME,
    description="CANARY sensor monitoring",
    lifespan=lifespan,
)

# backend status

@app.get("/status")
async def get_status(request: Request):
    pipeline = request.app.state.pipeline
    hardware_client = request.app.state.hardware_client
    listener_task = request.app.state.listener_task

    return {
        "application": APP_NAME,
        "hardware_connected": hardware_client.connected,
        "listener_running": not listener_task.done(),
        "processed_message_count": pipeline.message_count,
        "invalid_batch_count": pipeline.invalid_batch_count,
    }



# getting recent waveform data

@app.get("/waveforms/{sensor_name}")
def get_waveform(
    sensor_name: SensorName,
    request: Request,
    start_timestamp: float | None = Query(
        default=None,
        allow_inf_nan=False,
        description="Inclusive start time in unix seconds",
    ),
    end_timestamp: float | None = Query(
        default=None,
        allow_inf_nan=False,
        description="Inclusive end time in unix seconds",
    ),
):
    if (
        start_timestamp is not None
        and end_timestamp is not None
        and start_timestamp > end_timestamp
    ):
        raise HTTPException(
            status_code=422,
            detail="Start timestamp cannot be after end timestamp",
        )

    return request.app.state.pipeline.waveforms.get_waveform(
        sensor_name=sensor_name,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
    )


# reporting status

@app.get("/reporting/status")
async def get_reporting_status(request: Request):
    return request.app.state.pipeline.tiers.get_status()

