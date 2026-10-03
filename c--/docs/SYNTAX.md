# C Decrease Decrease — 语法参考手册 v-4

> **C++ 在加东西，C Decrease Decrease 在做减法。**
> 本手册与 `src/ccmm.py` 参考实现逐条对齐。每条语法旁边标注了它从哪个被砍尸还原而来。

---

## 0. 源文件与总体形态

| 项目 | 规定 |
|---|---|
| 扩展名 | `.ccm` |
| 编码 | UTF-8（注释和字符串里可以写中文） |
| 语句分隔 | **换行**。`;` 已被处决，写出即违法 |
| 块结构 | **缩进**（任意列数，同块对齐即可）。`{}` 已随分号殉葬 |
| 注释 | `#` 开头整行；行尾 `#` 也算——因为 `//` 一起被砍了 |
| 编译 | `python3 src/ccmm.py foo.ccm -o foo && ./foo` |
| 管线 | `.ccm → 生成的 C → 系统 cc → 原生二进制` |

空行无意义。文件顶部可放 `borrow` 声明，随后是若干 `func`。

---

## 1. 词法：关键字表

以下单词保留，不得用作标识符：

```
func loop until if elif else unless skip halt back borrow
pick case thunk default while let is isnt nothing maybe shout
text num none bool true false not new
```

其余一切标识符规则同 C（字母/数字/下划线，不能以数字开头）。

---

## 2. 类型：三原色

类型系统在被斧头劈过之后只剩三种本体类型（外加两个别名）：

| C--DD 类型 | 还原后的 C 类型 | 说明 |
|---|---|---|
| `num` | `long` | 整数。小数点？没砍但也没给，别问 |
| `text` | `const char*` | 字符串字面量与文本指针 |
| `none` | `void` | 什么都不返回，正如人生 |
| `bool` | `int` | `true`=1，`false`=0 |

`let` 绑定时若未显式标注类型，编译器按字面量**猜类型**（infer_type）：带引号→`text`，纯数字→`num`，其余透传给 C 赌运气。

> ☠️ **数组已殉职。** `new` 一词仍留在关键字名单里守灵，但 `let xs is new num[10]` 会当场编译失败——`[` 和 `]` 在 v-3 与分号一同下葬。想要"数组"请手写十个 `let`，这是教义，不是限制。

---

## 3. 表达式

### 3.1 比较运算符：`is` / `isnt`

```cdd
if x is 42:        # → if (x == 42)
unless x isnt 0:   # → if (!(x != 0))
```

⚠️ 注意：`is` 在**赋值语境**（`let x is ...`）里是"等于"，在**条件语境**里是 `==`。这是设计事故，不是特性。但我们拒绝修复，因为修复要加代码，加代码有违教义。

### 3.2 逻辑运算符：`&also` / `|else&` / `not`

```cdd
if a > 0 &also b < 10:      # → (a > 0 && b < 10)
if a is 1 |else& b is 2:    # → (a == 1 || b == 2)
if not flag:                # → (!flag)
```

记忆法：`&also` = "and, also"；`|else&` = "or else"（威胁语气）。它们长得像被斧头崩了边的 `&&` 和 `||`，这正是意图。

### 3.3 算术

`+ - / % *` 存活，另外 `%` 有一个更虔诚的写法：

```cdd
let r is n mod 15     # → long r = n % 15;
```

优先级完全继承 C，我们懒得重新发明，也懒得修 bug。

### 3.4 三元运算符：`maybe(cond, yes, no)`

`?:` 被砍后由 `maybe` 顶班，**恰好三个参数**，多一个少一个都编译失败：

```cdd
v = maybe(v > 50, v + 2, v - 2)   # → ((v > 50) ? (v + 2) : (v - 2))
```

名字来自薛定谔：在求值之前，结果既是 yes 又是 no。（实际上就是 C 三元，没有叠加态。）

### 3.5 指针：`p^` 解引用

`*p` 里的 `*` 被当作"多余的标点"砍掉了。解引用改为后缀指数记法：

```cdd
let p = &v          # 取地址 & 还活着（尚未轮到它受审）
shout("value {(*p)}")   # 老派手写 (*p) 也放行，照顾遗老
shout("value {(p^)}")   # 新派：p^ ≡ *p
```

> 内存的平方根是地址。（并不。别在面试里这么说。）

### 3.6 空指针：`nothing`

`NULL` 已死。空指针、空串终止符、以及你努力的意义，统一写作：

```cdd
let q is nothing       # → const char* q = NULL;
if q isnt nothing: ...
```

### 3.7 括号与函数调用

`( )` 存活（砍掉它编译器自己也没法生成 C），`f(a, b)` 调用语法同 C。

---

## 4. 语句

### 4.1 声明与赋值

```cdd
let answer is 42          # 首次绑定，必须 let
answer = 43               # 再赋值用 =，不带 let
let name is "world"       # text
let flag is true          # bool
```

一行一条。两行之间想连写？中间那个分号已经入土了。

### 4.2 输出：`shout(...)`

`printf` 改名 `shout`，因为轻声细语的 I/O 不配活到 v-4。两种模式：

```cdd
shout("plain text\n")             # 原样透传给 printf
shout("hi {name}, 2x={n*2}\n")    # 花括号插值：自动拆成 printf 格式串+实参
```

插值规则：字符串字面量中出现 `{expr}` 即触发；`expr` 按猜型结果自动选 `%ld` / `%s`。`\n` 需要手写——转义序列还没排上砍除日程。

### 4.3 条件：`if / elif / else:`

```cdd
if score is 100:
    shout("perfect\n")
elif score > 60:
    shout("passable\n")
else:
    shout("cry about it\n")
```

冒号 + 缩进块。`else:` 单独成行（写成 `else` 不带冒号会被拒，因为那是残缺的尸体）。

### 4.4 反向条件：`unless cond:`

`if (!cond)` 的考古复原件：

```cdd
unless q != nothing:
    shout("q is pure void\n")
```

### 4.5 计数循环：`loop i from A to B: ... until COND`

`for` 关键词连同它的三段式 header 一起火化。招魂仪式分两半，**隔着一个缩进块**：

```cdd
loop i from 1 to 20:
    classify(i)
until i > 20                     # 招魂词：until 一到，loop 安息
```

语义：`i` 从 A 起每轮 +1，块结束后检查 `until` 条件；循环继续的条件是 **`!(i > B) && !(until条件)`**——即上界 B 与招魂词 until 双重把关，任一为真即超度。展开示例（`loop i from 1 to 4: ... until i > 3`）：

```c
for (long i = 1; !(i > 4) && !(i > 3); i++) { /* 块 */ }
```

（注意：两个条件都出现在循环 header 里，且 `until` 在块之后才写、却每轮开头就被求值。是的，我们知道这很怪。教义不允许优化。）

### 4.6 条件循环：`while cond:`

```cdd
while v > 100:
    v = v / 2
```

### 4.7 循环控制：`skip` / `halt`

```cdd
loop i from 1 to 10:
    if i mod 2 is 0:
        skip          # continue：跳过本轮
    if i > 7:
        halt          # break：整个 loop 就地埋葬
    shout("{i} is odd and alive\n")
```

### 4.8 分支选择：`pick / case / thunk`

`switch` 的 `case/break` 双亡之后，由 `pick` 复活。每个分支必须以 `thunk:` 结尾——它是防 fallthrough 的裹尸布：

```cdd
pick n mod 15:
    case 0 thunk:
        shout("FizzBuzz\n")
    case 3, 6, 9, 12 thunk:
        shout("Fizz\n")
    default thunk:
        shout("{n}\n")
```

规则：`case` 后可跟逗号分隔的多值；忘记写 `thunk:` 视为异端，编译失败；fallthrough 物理不可能（codegen 自动补 `break`）。

### 4.9 返回：`back [expr]`

`return` 被砍成过去式：

```cdd
back 0        # return 0;
back          # return;（none 函数专用）
```

### 4.10 引用头文件：`borrow <name>`

`#include` 的 `#` 和 `include` 都被没收，改为向 C 标准库**借**：

```cdd
borrow <stdio>
borrow <math.h>
# 注意：C Decrease Decrease 的 <name> 不会自动补 .h——借 stdio 是历史豁免，
# 其余请自带扩展名，编译器对 header 名字不做任何仁慈的猜测
```

同名 header 只借一次。除了 `borrow`，没有任何办法进入 C 的世界——没有宏，没有链接指令，我们砍不动更多了。

---

## 5. 函数定义

```cdd
func classify(n is num) -> none:
    ...
func main() -> num:
    ...
    back 0
```

文法：

```
func 名字(形参表) -> 返回类型:
    缩进块
```

- 形参一律写成 `名字 is 类型`（`n is num`），逗号分隔；
- 返回类型必填（`-> none` 也要写，沉默是金但编译器是铜）；
- 行尾冒号是死刑执行人留下的最后一笔——缺冒号直接编译失败；
- 函数间无重载、无前向声明需求（先定义后使用，或全靠 main）。

---

## 6. 完整 EBNF（节选核心）

```ebnf
program   := { comment | borrow | func } ;
borrow    := "borrow" "<" header ">" NEWLINE ;
func      := "func" IDENT "(" [ params ] ")" "->" TYPE ":" NEWLINE block ;
params    := param { "," param } ;
param     := IDENT "is" TYPE ;
block     := INDENT statement+ DEDENT ;
statement := let | assign | shout | back | skip | halt
           | ifchain | unless | while | loop | pick | call | exprstmt ;
let       := "let" IDENT ("is"|":="|"=") expr ;
assign    := IDENT "=" expr ;
ifchain   := "if" expr ":" block { "elif" expr ":" block } [ "else:" block ] ;
unless    := "unless" expr ":" block ;
while     := "while" expr ":" block ;
loop      := "loop" IDENT "from" expr "to" expr ":" block "until" expr ;
pick      := "pick" expr ":" { "case" vals "thunk:" block }
             [ "default thunk:" block ] ;
shout     := "shout" "(" STRING_OR_ARGS ")" ;
back      := "back" [ expr ] ;
expr      := 见 §3（is/isnt/&also/|else&/mod/maybe/^/nothing 均为其一部分）;
```

---

## 7. 错误信息（精选博物馆藏品）

| 罪状 | 判决 |
|---|---|
| `maybe` 给了 4 个参数 | `maybe() wants 3 args, got 4` |
| `loop` 后面没找到 `until` | `loop lost its 'until' (we chop orphans)` |
| `func` 忘写冒号 | ``func needs `name(params) -> type:` (colon required, because we chopped almost everything else)`` |
| `case` 忘写 `thunk:` | `inside pick: only 'case v thunk:' or 'default thunk:' survive` |
| `borrow` 后没跟尖括号 | `borrow wants <header>, e.g. borrow <stdio>` |
| 后端 gcc 拒绝生成的 C | `c--: backend cc rejected our C. This is fine.` |

---

## 8. 快速对照表：C → C Decrease Decrease

| C | C--DD | 状态 |
|---|---|---|
| `;` | *(换行)* | ☠️ |
| `{ }` | 缩进 | ☠️ |
| `//` `/* */` | `#` | ☠️ |
| `==` / `!=` | `is` / `isnt` | ☠️ |
| `&&` / `\|\|` / `!` | `&also` / `\|else&` / `not` | ☠️ |
| `?:` | `maybe(c,a,b)` | ☠️ |
| `switch/case/break` | `pick/case…thunk/default thunk` | ☠️ |
| `for` | `loop…until` | ☠️ |
| `continue` / `break` | `skip` / `halt` | ☠️ |
| `return` | `back` | ☠️ |
| `NULL` | `nothing` | ☠️ |
| `*p` | `p^` | ☠️ |
| `#include` | `borrow` | ☠️ |
| `printf` | `shout`（+插值） | ☠️ |
| `int/char/float/double` | `num/text/none` | ☠️（float 阵亡） |
| `( )` `,` `=` `&` `while` `if` | 原样 | 🪚 幸存 |

---

*© C Decrease Decrease Foundation — 「我们删掉了 90% 的 C，剩下的 10% 全是 bug 的快乐。」*
*下一版本预告：v-5，计划删除 `main`。程序将从随机一行开始执行。*
