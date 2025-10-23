from audio_test import adc_passthrough_test, adc_passthrough_looping

def main() -> None:
    sample_rate = 16_000
    print(f"ADC passthrough sample rate: {sample_rate} Hz")
    # adc_passthrough_test(
    #     sample_rate=sample_rate,
    #     block_samples=512,
    #     gain=4.0,
    #     channel_count=2,
    #     debug=True,
    # )
    adc_passthrough_looping(
        sample_rate=sample_rate,
        block_samples=512,
        gain=2.0,
        debug=True
    )

if __name__ == "__main__":
    main()
