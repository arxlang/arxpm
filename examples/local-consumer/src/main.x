```
title: Consumer entry that imports from a sibling ``local_lib`` project.
```

import sum2 from local_lib.stats

fn main() -> i32:
  ```
  title: Print a deterministic value produced by the library helper
  ```
  print(sum2(2, 3));
  return 0;
