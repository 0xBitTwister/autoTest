from pytest_embedded import Dut


def test_basic_expect(redirect, dut: Dut):
    with redirect():
        print('this would be redirected')

    dut.expect('this')
    dut.expect_exact('would')
    dut.expect('[be]{2}')
    dut.expect_exact('redirected')