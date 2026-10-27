#pragma once

#include <pjsip.h>
#include <string>
#include <vector>

namespace alojan {
struct IdentityPolicy {
    std::vector<std::string> trusted_ips;
    bool from_first = false;
    bool turkish_national = false;
    void add_trusted_ip(const std::string &value);
};

struct NumberIdentity {
    std::string e164;
    std::string source = "none";
    std::string status = "unknown";
};

struct CallerIdentity {
    NumberIdentity caller;
    std::vector<NumberIdentity> redirects;
    bool trusted_source = false;
    bool pai_ignored = false;
    bool redirects_ignored = false;
    std::string log_fields() const;
};

// Only transport provenance may establish operator trust; no SIP header authenticates a caller.
CallerIdentity read_identity(const pjsip_rx_data &data, const IdentityPolicy &policy);

enum class CalledNumberSource { request_uri, to };
// Select one deployment-configured field. Never infer the destination from caller identity.
NumberIdentity read_called_number(const pjsip_rx_data &data, const IdentityPolicy &policy,
                                  CalledNumberSource source);
} // namespace alojan
