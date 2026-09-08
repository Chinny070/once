# v0.1.0
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *

import typing
from dataclasses import dataclass


ERR_EXPECTED = "EXPECTED"
MAX_NOTE_LEN = 400


@gl.contract_interface
class IOnce:
    class View:
        def is_executable(
            self,
            effect_id: u256,
            expected_profile_hash: str,
            expected_action_hash: str,
            expected_requester: Address,
            expected_consumer: Address,
        ) -> bool: ...

    class Write:
        pass


@allow_storage
@dataclass
class ExecutionReceipt:
    requester: Address
    effect_id: u256
    action_hash: str
    note: str


class EffectConsumed(gl.Event):
    def __init__(self, effect_id: u256, requester: Address, /, **blob): ...


class OnceProtectedExecutor(gl.Contract):
    """Minimal consumer proving Once permits are reusable across Intelligent Contracts."""

    once_address: Address
    execution_count: u256
    consumed: TreeMap[u256, bool]
    receipts: TreeMap[u256, ExecutionReceipt]

    def __init__(self, once_address: Address):
        self.once_address = once_address
        self.execution_count = u256(0)

    @gl.public.write
    def execute(
        self,
        effect_id: u256,
        expected_profile_hash: str,
        expected_action_hash: str,
        note: str,
    ) -> u256:
        if self.consumed.get(effect_id, False):
            raise gl.vm.UserError(f"{ERR_EXPECTED}: effect already consumed")
        note = " ".join(str(note).strip().split())[:MAX_NOTE_LEN]
        # Normalize to str: some calldata encoders present all-digit inputs as
        # ints. len() on int raises TypeError, so coerce before validating.
        expected_profile_hash = str(expected_profile_hash)
        expected_action_hash = str(expected_action_hash)
        if len(expected_profile_hash) != 64:
            raise gl.vm.UserError(f"{ERR_EXPECTED}: invalid profile hash")
        if len(expected_action_hash) < 16:
            raise gl.vm.UserError(f"{ERR_EXPECTED}: invalid action hash")

        requester = gl.message.sender_address
        allowed = IOnce(self.once_address).view().is_executable(
            effect_id,
            expected_profile_hash,
            expected_action_hash,
            requester,
            gl.message.contract_address,
        )
        if not allowed:
            raise gl.vm.UserError(f"{ERR_EXPECTED}: Once permit is not executable")

        self.consumed[effect_id] = True
        self.execution_count = u256(int(self.execution_count) + 1)
        receipt_id = self.execution_count
        self.receipts[receipt_id] = ExecutionReceipt(
            requester=requester,
            effect_id=effect_id,
            action_hash=expected_action_hash,
            note=note,
        )
        EffectConsumed(effect_id, requester, receipt_id=int(receipt_id)).emit()
        return receipt_id

    @gl.public.view
    def is_consumed(self, effect_id: u256) -> bool:
        return bool(self.consumed.get(effect_id, False))

    @gl.public.view
    def get_receipt(self, receipt_id: u256) -> dict[str, typing.Any]:
        receipt = self.receipts.get(receipt_id)
        if receipt is None:
            raise gl.vm.UserError(f"{ERR_EXPECTED}: unknown receipt")
        return {
            "receipt_id": int(receipt_id),
            "requester": receipt.requester.as_hex,
            "effect_id": int(receipt.effect_id),
            "action_hash": str(receipt.action_hash),
            "note": str(receipt.note),
        }
