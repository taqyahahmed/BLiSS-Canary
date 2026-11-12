import json
import logging
import math

from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("canary.websocket_receiver")


def validate_batch(batch):

    if not isinstance(batch, dict):
        return False, "Batch must be a JSON object."

    if batch.get("type") != "batch":
        return False, "Expected a batch message."

    if not batch.get("device_id"):
        return False, "Missing device_id."

    if not isinstance(batch.get("sequence_number"), int):
        return False, "Invalid sequence_number."

    try:
        timestamp = datetime.fromisoformat(
            batch["timestamp"].replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            return False, "Timestamp must include a timezone."

    except (ValueError, TypeError, AttributeError):
        return False, "Invalid timestamp."

    samples = batch.get("samples")

    if not isinstance(samples, dict):
        return False, "Samples must be an object."

    for sensor, values in samples.items():

        if not isinstance(values, list):
            return False, f"{sensor} samples must be a list."

        for value in values:

            if isinstance(value, bool):
                return False, f"{sensor} values must be numeric."

            if not isinstance(value, (int, float)):
                return False, f"{sensor} values must be numeric."

            if not math.isfinite(value):
                return False, f"{sensor} values must be finite."

    summary = batch.get("summary")

    if not isinstance(summary, dict):
        return False, "Summary must be an object."

    for sensor, features in summary.items():

        if not isinstance(features, dict):
            return False, f"Invalid summary for {sensor}."

        for feature in ("mean", "minimum", "maximum", "std"):
            value = features.get(feature)

            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                return False, f"Invalid {feature} for {sensor}."

    return True, None


async def receive_sensor_data(websocket: WebSocket):

    await websocket.accept()

    logger.info("CANARY WebSocket connection established.")

    try:

        while True:

            raw_message = await websocket.receive_text()

            try:
                batch = json.loads(raw_message)

            except json.JSONDecodeError:

                await websocket.send_json({
                    "type": "error",
                    "detail": "Invalid JSON."
                })

                continue

            valid, error = validate_batch(batch)

            if not valid:

                await websocket.send_json({
                    "type": "error",
                    "detail": error
                })

                continue

            logger.info(
                "Received batch %s from %s. Samples: %s",
                batch["sequence_number"],
                batch["device_id"],
                {
                    sensor: len(values)
                    for sensor, values in batch["samples"].items()
                }
            )

            # Database integration will be added here.
            # Preserve batch["samples"] for raw data storage.
            # Preserve batch["summary"] for feature storage.

            await websocket.send_json({
                "type": "ack",
                "received": True,
                "sequence_number": batch["sequence_number"]
            })

    except WebSocketDisconnect:

        logger.info("CANARY WebSocket disconnected.")