#include "caller_identity.hpp"

#include <algorithm>
#include <arpa/inet.h>
#include <optional>
#include <pjsip/sip_tel_uri.h>
#include <stdexcept>
#include <string_view>

namespace alojan {
namespace {
std::string text(const pj_str_t &value) {
    return value.slen > 0 ? std::string(value.ptr, value.slen) : std::string{};
}

std::string lower(std::string value) {
    for (auto &c : value)
        if (c >= 'A' && c <= 'Z')
            c += 'a' - 'A';
    return value;
}

bool digits(std::string_view value) {
    return !value.empty() &&
           std::all_of(value.begin(), value.end(), [](char c) { return c >= '0' && c <= '9'; });
}

std::optional<std::string> normalize(std::string value, const IdentityPolicy &policy) {
    if (value.size() > 64)
        return {};
    // Only telephone visual separators are removed; never discard arbitrary characters.
    std::erase_if(value, [](char c) { return c == '-' || c == '.' || c == '(' || c == ')'; });
    if (value.starts_with("00"))
        value = "+" + value.substr(2);
    if (policy.turkish_national && digits(value)) {
        if (value.size() == 11 && value.front() == '0')
            value.erase(0, 1);
        if (value.size() == 10)
            value = "+90" + value;
        else if (value.size() == 12 && value.starts_with("90"))
            value = "+" + value;
    }
    if (value.size() < 3 || value.size() > 16 || value.front() != '+' || value[1] == '0' ||
        !digits(std::string_view(value).substr(1)))
        return {};
    if (value.starts_with("+90") && (value.size() != 13 || value[3] < '2' || value[3] > '9'))
        return {};
    return value;
}

NumberIdentity uri_number(pjsip_uri *wrapped, const IdentityPolicy &policy) {
    NumberIdentity result;
    if (!wrapped) {
        result.status = "invalid";
        return result;
    }
    auto *uri = static_cast<pjsip_uri *>(pjsip_uri_get_uri(wrapped));
    std::string number;
    if (PJSIP_URI_SCHEME_IS_SIP(uri) || PJSIP_URI_SCHEME_IS_SIPS(uri)) {
        const auto *sip = reinterpret_cast<pjsip_sip_uri *>(uri);
        number = text(sip->user);
        if (lower(text(sip->host)) == "anonymous.invalid" || lower(number) == "anonymous") {
            result.status = "anonymous";
            return result;
        }
        if (sip->passwd.slen || !pj_list_empty(&sip->header_param)) {
            result.status = "invalid";
            return result;
        }
    } else if (PJSIP_URI_SCHEME_IS_TEL(uri)) {
        const auto *tel = reinterpret_cast<pjsip_tel_uri *>(uri);
        number = text(tel->number);
        // shortcut: only the +90 national phone-context is supported; extend with carrier evidence.
        if (tel->context.slen) {
            if (text(tel->context) != "+90" || number.starts_with("+") ||
                !policy.turkish_national) {
                result.status = "invalid";
                return result;
            }
        }
        if (tel->ext_param.slen || tel->isub_param.slen) {
            result.status = "invalid";
            return result;
        }
    } else {
        result.status = "invalid";
        return result;
    }
    const auto token = lower(number);
    if (token == "anonymous")
        result.status = "anonymous";
    else if (token == "withheld" || token == "restricted")
        result.status = "withheld";
    else if (token.empty() || token == "unknown" || token == "unavailable")
        result.status = "unknown";
    else if (auto canonical = normalize(number, policy)) {
        result.e164 = *canonical;
        result.status = "available";
    } else
        result.status = "invalid";
    return result;
}

bool hidden(const NumberIdentity &number) {
    return number.status == "anonymous" || number.status == "withheld";
}

bool private_header(const std::string &value) {
    std::size_t start = 0;
    while (start < value.size()) {
        const auto end = value.find(';', start);
        auto token = lower(value.substr(start, end - start));
        const auto first = token.find_first_not_of(" \t\r\n");
        if (first == std::string::npos)
            return true;
        token = token.substr(first, token.find_last_not_of(" \t\r\n") - first + 1);
        // Unknown privacy extensions fail closed; 'none' cannot override another privacy token.
        if (token != "none" && token != "session")
            return true;
        if (end == std::string::npos)
            return false;
        start = end + 1;
    }
    return true;
}

std::vector<NumberIdentity> address_list(pj_pool_t *pool, std::string value,
                                         const std::string &source, const IdentityPolicy &policy) {
    const std::vector<NumberIdentity> invalid{{"", source, "invalid"}};
    if (value.empty() || value.size() > 1024 || value.find('\0') != std::string::npos)
        return invalid;
    // Contact reuses PJSIP's name-address list grammar, including quoted commas and parameters.
    auto name = pj_str(const_cast<char *>("Contact"));
    int parsed = 0;
    auto *first = static_cast<pjsip_contact_hdr *>(
        pjsip_parse_hdr(pool, &name, value.data(), value.size(), &parsed));
    if (!first || parsed != static_cast<int>(value.size()))
        return invalid;
    std::vector<NumberIdentity> result;
    auto *entry = first;
    do {
        if (entry->star || result.size() == 8)
            return invalid;
        auto number = uri_number(entry->uri, policy);
        number.source = source;
        for (auto *param = entry->other_param.next; param != &entry->other_param;
             param = param->next)
            if (lower(text(param->name)) == "privacy" && lower(text(param->value)) != "off") {
                number.e164.clear();
                number.status = "withheld";
            }
        result.push_back(std::move(number));
        entry = entry->next;
    } while (entry != first);
    return result;
}

NumberIdentity asserted(const std::vector<NumberIdentity> &numbers) {
    NumberIdentity result{"", "pai", "unknown"};
    for (const auto &number : numbers)
        if (hidden(number))
            return number;
    for (const auto &number : numbers) {
        if (number.status != "available")
            return {"", "pai", "invalid"};
        if (!result.e164.empty() && result.e164 != number.e164)
            return {"", "pai", "ambiguous"};
        result = number;
    }
    return result;
}
} // namespace

void IdentityPolicy::add_trusted_ip(const std::string &value) {
    in_addr address{};
    char canonical[INET_ADDRSTRLEN]{};
    if (trusted_ips.size() == 16 || inet_pton(AF_INET, value.c_str(), &address) != 1 ||
        !inet_ntop(AF_INET, &address, canonical, sizeof(canonical)))
        throw std::invalid_argument("trusted identity IP must be an IPv4 literal (maximum 16)");
    trusted_ips.emplace_back(canonical);
}

CallerIdentity read_identity(const pjsip_rx_data &data, const IdentityPolicy &policy) {
    CallerIdentity result;
    if (!data.msg_info.msg || !data.tp_info.pool)
        return result;
    char ip[PJ_INET6_ADDRSTRLEN]{};
    pj_sockaddr_print(&data.pkt_info.src_addr, ip, sizeof(ip), 0);
    result.trusted_source = std::find(policy.trusted_ips.begin(), policy.trusted_ips.end(), ip) !=
                            policy.trusted_ips.end();
    NumberIdentity from;
    unsigned from_count = 0;
    std::vector<NumberIdentity> pai;
    bool privacy = false, overflow = false;
    unsigned identity_headers = 0;
    const auto *msg = data.msg_info.msg;
    for (auto *hdr = msg->hdr.next; hdr != &msg->hdr; hdr = hdr->next) {
        if (hdr->type == PJSIP_H_FROM) {
            ++from_count;
            from = uri_number(reinterpret_cast<pjsip_from_hdr *>(hdr)->uri, policy);
            from.source = "from";
            privacy = privacy || hidden(from);
            continue;
        }
        const auto name = lower(text(hdr->name));
        if (name != "privacy" && name != "p-asserted-identity" && name != "diversion" &&
            name != "history-info")
            continue;
        if (++identity_headers > 16 || hdr->type != PJSIP_H_OTHER) {
            overflow = true;
            continue;
        }
        const auto &raw = reinterpret_cast<pjsip_generic_string_hdr *>(hdr)->hvalue;
        if (raw.slen > 1024) {
            overflow = true;
            continue;
        }
        if (name == "privacy") {
            privacy = privacy || private_header(text(raw));
            continue;
        }
        if (!result.trusted_source) {
            result.pai_ignored |= name == "p-asserted-identity";
            result.redirects_ignored |= name != "p-asserted-identity";
            continue;
        }
        const bool is_pai = name == "p-asserted-identity";
        auto values = address_list(data.tp_info.pool, text(raw), is_pai ? "pai" : name, policy);
        auto &target = is_pai ? pai : result.redirects;
        if (target.size() + values.size() > 8)
            overflow = true;
        else
            target.insert(target.end(), values.begin(), values.end());
    }
    if (from_count != 1)
        from = {"", "from", from_count ? "ambiguous" : "unknown"};
    const auto trusted = asserted(pai);
    privacy = privacy || hidden(trusted);
    if (privacy) {
        result.caller = {"", "none",
                         (from.status == "anonymous" || trusted.status == "anonymous")
                             ? "anonymous"
                             : "withheld"};
        result.redirects.clear();
    } else if (overflow) {
        result.caller = {"", "none", "invalid"};
        result.redirects.clear();
    } else if (!pai.empty() && !(policy.from_first && from.status == "available"))
        result.caller = trusted;
    else
        result.caller = from;
    return result;
}

std::string CallerIdentity::log_fields() const {
    return "identity_status=" + caller.status + " identity_source=" + caller.source +
           " caller_number=" + (caller.e164.empty() ? "unknown" : "redacted") +
           " operator_trusted=" + (trusted_source ? "1" : "0") +
           " pai_ignored=" + (pai_ignored ? "1" : "0") +
           " redirects=" + std::to_string(redirects.size()) +
           " redirects_ignored=" + (redirects_ignored ? "1" : "0");
}
} // namespace alojan
