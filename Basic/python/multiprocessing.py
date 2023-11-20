'''
The built-in multiprocessing module in Python allows us to run more than 1 function concurrently (at the same time).
'''
import multiprocessing
import time
import datetime

def yourfunction(x):
    start = datetime.datetime.now()
    time.sleep(1)
    end = datetime.datetime.now()
    return f'x={x} start at {start}, end at {end}'

if __name__ == '__main__':
    with multiprocessing.Pool(processes=3) as pool:
        data = pool.map(yourfunction, [1, 2, 3, 4, 5, 6, 7])

    for row in data:
        print(row)


# x=1 start at 2023-08-13 00:25:38.540964, end at 2023-08-13 00:25:39.543490
# x=2 start at 2023-08-13 00:25:38.541006, end at 2023-08-13 00:25:39.543500
# x=3 start at 2023-08-13 00:25:38.541088, end at 2023-08-13 00:25:39.543504
# x=4 start at 2023-08-13 00:25:39.543995, end at 2023-08-13 00:25:40.547278
# x=5 start at 2023-08-13 00:25:39.544148, end at 2023-08-13 00:25:40.547295
# x=6 start at 2023-08-13 00:25:39.544318, end at 2023-08-13 00:25:40.547284
# x=7 start at 2023-08-13 00:25:40.547419, end at 2023-08-13 00:25:41.550812
