#pragma once

#include <grpcpp/channel.h>
#include <memory>
#include <string>

namespace alojan {
// CallSetup owns release; consumers borrow the exact configured worker/lease.
struct CallServiceBinding {
    std::shared_ptr<grpc::Channel> channel;
    std::string call_id, lease;
};
} // namespace alojan
