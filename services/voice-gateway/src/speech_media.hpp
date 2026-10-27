#pragma once

#include "input_meter.hpp"
#include "prepared_audio.hpp"
#include "speech_bridge.hpp"
#include <stdexcept>

class SpeechInput : public InputMeter {
  public:
    alojan::SpeechBridge *bridge = nullptr;
    void onFrameReceived(pj::MediaFrame &frame) override {
        InputMeter::onFrameReceived(frame);
        if (bridge && frame.type == PJMEDIA_FRAME_TYPE_AUDIO && frame.buf.size() == 640)
            bridge->receive(reinterpret_cast<const char *>(frame.buf.data()));
    }
};

// Use PJMEDIA's supplied buffer: the PJSUA2 vector callback would allocate every 20 ms.
template <class Renderer> class PcmOutput : public pj::AudioMedia {
    struct Data {
        pj_pool_t *pool;
        Renderer *bridge;
    };
    pjmedia_port *port_ = nullptr;

    static pj_status_t get_frame(pjmedia_port *port, pjmedia_frame *frame) {
        auto *data = static_cast<Data *>(port->port_data.pdata);
        pj_grp_lock_acquire(port->grp_lock);
        if (frame->size >= 320) {
            if (!data->bridge || !data->bridge->render(static_cast<char *>(frame->buf)))
                std::memset(frame->buf, 0, 320);
            frame->type = PJMEDIA_FRAME_TYPE_AUDIO;
            frame->size = 320;
        } else {
            frame->type = PJMEDIA_FRAME_TYPE_NONE;
            frame->size = 0;
        }
        pj_grp_lock_release(port->grp_lock);
        return PJ_SUCCESS;
    }
    static pj_status_t destroy(pjmedia_port *port) {
        auto *data = static_cast<Data *>(port->port_data.pdata);
        pj_pool_release(data->pool);
        return PJ_SUCCESS;
    }

  public:
    void create(Renderer &bridge) {
        auto *pool = pjsua_pool_create("speech-output", 512, 512);
        if (!pool)
            throw std::runtime_error("speech port allocation failed");
        port_ = PJ_POOL_ZALLOC_T(pool, pjmedia_port);
        auto *data = PJ_POOL_ZALLOC_T(pool, Data);
        data->pool = pool;
        data->bridge = &bridge;
        port_->port_data.pdata = data;
        pj_str_t name = pj_str(const_cast<char *>("speech-output"));
        pjmedia_port_info_init(&port_->info, &name, PJMEDIA_SIG_CLASS_APP('A', 'L', 'O'), 8000, 1,
                               16, 160);
        port_->get_frame = &get_frame;
        port_->on_destroy = &destroy;
        if (pjmedia_port_init_grp_lock(port_, pool, nullptr) != PJ_SUCCESS) {
            port_ = nullptr;
            pj_pool_release(pool);
            throw std::runtime_error("speech port lifecycle initialization failed");
        }
        registerMediaPort2(port_, pool);
    }
    ~PcmOutput() override {
        if (!port_)
            return;
        try {
            unregisterMediaPort();
        } catch (const pj::Error &) {
        }
        // Mirror PJSUA2's group-lock lifetime guard: conference removal is asynchronous.
        pj_grp_lock_acquire(port_->grp_lock);
        static_cast<Data *>(port_->port_data.pdata)->bridge = nullptr;
        pj_grp_lock_release(port_->grp_lock);
        pjmedia_port_destroy(port_);
    }
};

using SpeechOutput = PcmOutput<alojan::SpeechBridge>;
using PreparedOutput = PcmOutput<alojan::PreparedPlayback>;
