import os
import time

try:
    iterations = int(os.getenv('COUNT', '5'))
except:
    print("Defaulting to 5 iterations.")
    iterations = 5

print("Doing stuff...")
for i in range(0, iterations):
    print('.', end='', flush=True)
    if i % 10 == 9:
        print()
    time.sleep(1)
print()
print("Stuff has been done.")
