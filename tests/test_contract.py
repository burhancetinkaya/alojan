import pytest
from google.protobuf.descriptor import FieldDescriptor as Field
from voice.v1 import voice_pb2 as pb


@pytest.mark.parametrize(
    "message,fields",
    [
        (
            pb.TurnEvent,
            [
                ("call_id", 1, Field.TYPE_STRING),
                ("generation_id", 2, Field.TYPE_STRING),
                ("type", 3, Field.TYPE_STRING),
                ("at_unix_ms", 4, Field.TYPE_INT64),
                ("confidence", 5, Field.TYPE_FLOAT),
                ("detail_json", 6, Field.TYPE_STRING),
            ],
        ),
        (
            pb.AgentRequest,
            [
                ("call_id", 1, Field.TYPE_STRING),
                ("generation_id", 2, Field.TYPE_STRING),
                ("final_user_text", 3, Field.TYPE_STRING),
                ("context_json", 4, Field.TYPE_STRING),
            ],
        ),
        (
            pb.AgentEvent,
            [
                ("call_id", 1, Field.TYPE_STRING),
                ("generation_id", 2, Field.TYPE_STRING),
                ("type", 3, Field.TYPE_STRING),
                ("text", 4, Field.TYPE_STRING),
                ("detail_json", 5, Field.TYPE_STRING),
            ],
        ),
    ],
)
def test_core_messages_preserve_baseline_wire_types(message, fields):
    assert [(f.name, f.number, f.type) for f in message.DESCRIPTOR.fields] == fields


def test_binary_audio_preserves_identity_and_format():
    frame = pb.AudioFrame(
        call_id="call-a",
        generation_id="generation-2",
        sequence=42,
        captured_at_unix_ms=1000,
        sample_rate_hz=8000,
        channels=1,
        format="pcm_s16le",
        audio=b"\x00\x80\xff\x7f",
    )
    restored = pb.AudioFrame.FromString(frame.SerializeToString())
    assert restored == frame
    assert restored.audio == b"\x00\x80\xff\x7f"


def test_field_numbers_remain_wire_compatible():
    expected = {
        "call_id": 1,
        "sequence": 2,
        "captured_at_unix_ms": 3,
        "sample_rate_hz": 4,
        "channels": 5,
        "format": 6,
        "audio": 7,
        "generation_id": 8,
    }
    assert {f.name: f.number for f in pb.AudioFrame.DESCRIPTOR.fields} == expected
    assert [f.type for f in pb.AudioFrame.DESCRIPTOR.fields] == [
        Field.TYPE_STRING,
        Field.TYPE_UINT64,
        Field.TYPE_INT64,
        Field.TYPE_UINT32,
        Field.TYPE_UINT32,
        Field.TYPE_STRING,
        Field.TYPE_BYTES,
        Field.TYPE_STRING,
    ]
    services = pb.DESCRIPTOR.services_by_name
    recognition = services["Recognition"].methods[0]
    assert recognition.client_streaming and recognition.server_streaming
    assert services["Synthesis"].methods[0].server_streaming
    assert not services["Synthesis"].methods[0].client_streaming
    assert services["Agent"].methods[0].server_streaming
    assert not services["Agent"].methods[0].client_streaming
    assert not services["GenerationControl"].methods[0].server_streaming
    assert not services["GenerationControl"].methods[0].client_streaming
