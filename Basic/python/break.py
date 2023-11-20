for i in [1,2,3,4,5]:
  if i == 3:
    break
  print(i)

# this prints 1 and 2

for i in [1,2,3,4,5]:
  if i == 3:
    continue
  print(i)

# this prints 1, 2, 4 and 5

for i in [1,2,3,4,5]:
  if i == 3:
    pass
  print(i)

# this prints 1, 2, 3, 4 and 5
