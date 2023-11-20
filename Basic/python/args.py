def myfunction(a, b, *args):
  print(f'{a=} {b=} {args=}')

myfunction(1,2,3,4,5)    # a=1 b=2 args=(3, 4, 5)

def myfunction(a, b, **kwargs):
  print(f'{a=} {b=} {kwargs=}')

myfunction(a=1, b=2, c=3, d=4)    # a=1 b=2 kwargs={'c': 3, 'd': 4}
