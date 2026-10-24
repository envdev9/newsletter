"""Wlasne filtry Jinja2 - Ansible sam ladowal filter_plugins/ obok playbooka."""
from ansible.errors import AnsibleFilterError


def mask_secret(value, visible=2, mask="*"):
    """'tajnehaslo' -> 'ta********' (zostaw `visible` pierwszych znakow)."""
    if not isinstance(value, str):
        raise AnsibleFilterError("mask_secret oczekuje stringa, dostal: %s" % type(value).__name__)
    if visible < 0:
        raise AnsibleFilterError("mask_secret: visible nie moze byc ujemne")
    return value[:visible] + mask * max(len(value) - visible, 0)


def to_env_lines(data, prefix=""):
    """{'a': 1, 'b': 'x'} -> ['PREFIX_A=1', 'PREFIX_B=x'] (posortowane po kluczu)."""
    if not isinstance(data, dict):
        raise AnsibleFilterError("to_env_lines oczekuje slownika")
    return ["%s%s=%s" % (prefix, key.upper(), data[key]) for key in sorted(data)]


class FilterModule(object):
    def filters(self):
        return {
            "mask_secret": mask_secret,
            "to_env_lines": to_env_lines,
        }
