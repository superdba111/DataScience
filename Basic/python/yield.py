def simple_generator():
  yield 'apple'
  yield 'orange'
  yield 'pear'

for fruit in simple_generator():
  print(fruit)

# apple 
# orange
# pear

'''
In normal functions, the return statement outputs something, and everything else in the function stops completely.
In generator functions, the yield statement outputs something, but the function doesn’t stop, and continues running. Until the end of the function, or until it reaches a return statement.
'''
