```
title: Multi-module entry point
```

import add from math_utils
import greet from string_utils

fn main() -> i32:
  ```
  title: Call functions imported from sibling modules
  returns:
    type: i32
  ```
  print(greet("Arx"));
  print(add(2, 3));
  return 0;
