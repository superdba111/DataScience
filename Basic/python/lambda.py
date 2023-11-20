def add(x, y):
  return x + y

# this is the same as 

add = lambda x,y : x+y

##########################################

def avg(a, b, c):
  return (a+b+c)/3

# this is the same as

avg = lambda a,b,c : (a+b+c)/3

############################################
def higher_order_function(x, myfunction):
  # stuff

# CASE 1: not using lambda functions
def myfunction(x):
  return x + 10

higher_order_function(100, myfunction)

# CASE 2: using lambda functions
higher_order_function(100, lambda x:x+10)
