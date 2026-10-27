#pragma once
#include "interruption.hpp"
#include "turn_detector.hpp"
#include "voice/v1/voice.pb.h"
#include <stdexcept>

namespace alojan {
struct OutputBudget {
    unsigned phrase_max_chars = 240, phrase_max_bytes = 1024;
    unsigned max_phrases = 16, turn_max_bytes = 4096;

    void validate() const {
        if (phrase_max_chars < 40 || phrase_max_chars > 240 || phrase_max_bytes < 160 ||
            phrase_max_bytes > 1024 || max_phrases < 1 || max_phrases > 16 ||
            turn_max_bytes < 1024 || turn_max_bytes > 4096 ||
            4 * phrase_max_chars > phrase_max_bytes || phrase_max_bytes > turn_max_bytes)
            throw std::invalid_argument("unsupported output limits");
    }
};

struct GatewaySettings {
    unsigned max_call_seconds = 120, answer_delay_ms = 3000;
    unsigned closing_delay_ms = 3000, media_drain_ms = 150;
    unsigned max_call_turns = 16, turn_timeout_seconds = 20;
    OutputBudget output{};
    TurnSettings turn{};
    InterruptionSettings interruption{};

    void validate() const {
        if (max_call_seconds < 10 || max_call_seconds > 300 || answer_delay_ms > 5000 ||
            closing_delay_ms > 5000 || media_drain_ms > 1000 || max_call_turns < 1 ||
            max_call_turns > 16 || turn_timeout_seconds < 1 || turn_timeout_seconds > 20)
            throw std::invalid_argument("unsupported gateway limits");
        output.validate();
        turn.validate();
        interruption.validate();
    }

    static GatewaySettings from_proto(const voice::v1::GatewayConfiguration &value) {
        if (value.schema_version() != 1 || value.ByteSizeLong() > 256 ||
            value.calibration().schema_version() != 1 || value.output().schema_version() != 1)
            throw std::invalid_argument("unsupported gateway configuration");
        GatewaySettings result{value.max_call_seconds(), value.answer_delay_ms(),
                               value.closing_delay_ms(), value.media_drain_ms(),
                               value.max_call_turns(),   value.turn_timeout_seconds()};
        const auto &output = value.output();
        result.output = {output.phrase_max_chars(), output.phrase_max_bytes(), output.max_phrases(),
                         output.turn_max_bytes()};
        const auto &calibration = value.calibration();
        result.turn = {calibration.partial_hint(),  calibration.vad_percent(),
                       calibration.candidate_ms(),  calibration.yes_no_ms(),
                       calibration.open_ms(),       calibration.uncertain_ms(),
                       calibration.incomplete_ms(), calibration.silence_reminder_ms()};
        result.interruption = {
            calibration.interrupt_vad_percent(), calibration.interrupt_min_voice_ms(),
            calibration.interrupt_sustained_voice_ms(), calibration.interrupt_max_quiet_ms(),
            calibration.interrupt_sustained_quiet_ms()};
        result.validate();
        return result;
    }

    unsigned closing_wait_ms(bool farewell) const {
        return media_drain_ms + (farewell ? closing_delay_ms : 0);
    }
};
} // namespace alojan
