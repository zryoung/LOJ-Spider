from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3), reraise=True)
def do_something():
    print("Doing something...")
    raise Exception("Something went wrong!")

try:
    do_something()
except Exception as e:
    print(f"Exception: {e}")

