CURSOR_UP = '\033[1A'
CLEAR = '\x1b[2K'
CLEAR_LINE = CURSOR_UP + CLEAR

print('apple')
print('orange')
print('pear')

# clears TWO lines
print(CLEAR_LINE * 2, end='')
print('pineapple')

# apple
# pineapple

