from hardware.platform.keypad_4x4 import Keypad4x4, KeypadPins
from signal import pause

def main():
    pins = KeypadPins(
        row1=12,
        row2=16,
        row3=20,
        row4=21,
        col1=5,
        col2=6,
        col3=13,
        col4=19,
    )

    keypad = Keypad4x4(pins)

    keypad.on_key = lambda k: print(f"[TEST] touche = {k}")
    keypad.start()

    print("Clavier prêt. Appuie sur des touches (CTRL+C pour quitter).")
    pause()

if __name__ == "__main__":
    main()
