import os
from config import RESULT_FILE

def main():
    if os.path.exists(RESULT_FILE) and os.path.isfile(RESULT_FILE):
        with open(RESULT_FILE, 'r') as file:
            content = file.readlines()
        if len(content) > 0:
            print(int(content[0].strip()))
        else:
            print("No result")
    else:
        print("No result")


if __name__ == "__main__":
    main()