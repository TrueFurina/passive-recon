"""R2 四层开关 / 计数 / 挂起。"""
from passive_agent.verifier.model import VerifyRequest, VerifyStatus
from passive_agent.verifier.pipeline import VerificationPipeline


def test_all_pass():
    p = VerificationPipeline()
    vr = p.run(VerifyRequest(
        result_id="r1", layer1_biz_match=True, layer2_dns_alive=True,
        layer3_time_ok=True, layer4_src_cnt=2))
    assert vr.status == VerifyStatus.PASS
    assert vr.fail_layer is None
    assert len(vr.layers) == 4


def test_single_source_suspend():
    p = VerificationPipeline()
    vr = p.run(VerifyRequest(
        result_id="r2", layer1_biz_match=True, layer2_dns_alive=True,
        layer3_time_ok=True, layer4_src_cnt=1))
    assert vr.status == VerifyStatus.SUSPEND
    assert vr.fail_layer == 4  # 单源挂起 -> 060001


def test_layer1_fail_suspend():
    p = VerificationPipeline()
    vr = p.run(VerifyRequest(
        result_id="r3", layer1_biz_match=False, layer2_dns_alive=True,
        layer3_time_ok=True, layer4_src_cnt=3))
    assert vr.status == VerifyStatus.SUSPEND
    assert vr.fail_layer == 1


def test_layer_toggle():
    p = VerificationPipeline()
    p.set_layer_enabled(4, False)
    vr = p.run(VerifyRequest(
        result_id="r4", layer1_biz_match=True, layer2_dns_alive=True,
        layer3_time_ok=True, layer4_src_cnt=1))
    # L4 关闭 -> 不参与校验 -> 通过
    assert vr.status == VerifyStatus.PASS
    c = p.counters()
    assert c[4] == 0  # 关闭层不计数
    assert c[1] >= 1 and c[2] >= 1 and c[3] >= 1
