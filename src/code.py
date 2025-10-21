import board
from device_controller import DeviceController


def main() -> None:
    controller = DeviceController(board_module=board, debug=True)
    controller.initialize()
    controller.run_forever()

if __name__ == "__main__":
    main()
