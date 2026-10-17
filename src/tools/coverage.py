def list_policies(policies) -> list[dict]:
    return [{"policy_id": p.policy_id, "name": p.name, "premium_annual": p.premium_annual,
             "currency": p.currency} for p in policies]


def get_coverage(policies, policy_id: str) -> dict:
    for p in policies:
        if p.policy_id == policy_id:
            return {"policy_id": p.policy_id, "name": p.name, "premium_annual": p.premium_annual,
                    "currency": p.currency,
                    "coverages": [c.model_dump() for c in p.coverages]}
    raise ValueError(f"Unknown policy_id: {policy_id}")
