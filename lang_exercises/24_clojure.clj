;; ============================================================
;; 阶段：Lisp函数式语言 - Clojure语言练习
;; 题数：2题
;; 创建日期：2026-08-05
;; ============================================================

;; ============================================================
;; 第1题：Clojure基础（S-expression / 不可变数据 / 序列抽象）
;; ============================================================
;; 知识点讲解：
;; Clojure是运行在JVM上的Lisp方言，核心特征：
;;   - S表达式(S-expression)：代码以括号包围的前缀表达式书写
;;     语法形式：(操作符 操作数1 操作数2 ...)
;;     例如：(+ 1 2 3) 表示 1+2+3
;;   - 代码即数据(Homoiconicity)：代码本身就是列表数据结构，
;;     这是宏系统的基础
;;   - 不可变数据(Immutable Data)：所有数据结构不可变
;;     "修改"操作返回新版本，利用结构共享避免完整复制
;;   - 持久化数据结构(Persistent Data Structure)：
;;     Clojure的向量、Map、集合都是持久化的，修改O(log32 n)时间
;;   - 序列抽象(Sequence Abstraction)：
;;     所有集合都可以视为序列(seq)，统一用map/filter/reduce操作
;;   - 惰性序列(Lazy Sequence)：lazy-seq创建惰性序列，按需计算

;; --- S表达式基础 ---
;; 前缀表达式：操作符在前面，操作数在后面

;; 基本算术
(+ 1 2 3)              ;; 6 — 加法可以接受任意多个参数
(- 10 3 2)             ;; 5 — 10-3-2
(* 2 3 4)              ;; 24
(/ 10 3)               ;; 10/3 — 精确分数(Clojure支持)
(/ 10.0 3)             ;; 3.333... — 浮点除法
(mod 10 3)             ;; 1 — 取模
(quot 10 3)            ;; 3 — 商
(inc 5)                ;; 6 — 加1
(dec 5)                ;; 4 — 减1

;; 比较运算
(= 1 1)                ;; true
(not= 1 2)             ;; true
(< 1 2 3)              ;; true — 可以链式比较
(<= 1 1 2)             ;; true
(> 5 3 1)              ;; true

;; 逻辑运算
(and true false)       ;; false
(or false true)        ;; true
(not true)             ;; false

;; --- def：定义变量 ---
(def x 42)
(def name "Clojure")
(def pi 3.14159)

(println "=== 基本变量 ===")
(println "x =" x)
(println "name =" name)
(println "pi =" pi)

;; --- 数据结构 ---
;; Clojure的核心数据结构都是不可变的

;; 1. 向量(Vector)：类似数组，索引访问O(1)
(def vec1 [1 2 3 4 5])
(def vec2 (vector 10 20 30))

(println "\n=== 向量 ===")
(println "vec1 =" vec1)
(println "第一个:" (first vec1))         ;; 1
(println "第二个:" (nth vec1 1))         ;; 2
(println "最后:" (last vec1))            ;; 5
(println "添加元素:" (conj vec1 6))      ;; [1 2 3 4 5 6]
(println "更新元素:" (assoc vec1 0 99))  ;; [99 2 3 4 5]

;; 2. 列表(List)：链表，头部操作O(1)
(def lst '(1 2 3 4 5))
(println "\n=== 列表 ===")
(println "lst =" lst)
(println "头部添加:" (conj lst 0))       ;; (0 1 2 3 4 5) — 列表从头部添加

;; 3. 映射(Map)：键值对
(def person {:name "Alice" :age 30 :city "NYC"})
(def person2 (hash-map :name "Bob" :age 25))

(println "\n=== Map ===")
(println "person =" person)
(println "名字:" (:name person))         ;; 关键字作为函数获取值
(println "年龄:" (get person :age))
(println "默认值:" (get person :country "未知"))
(println "更新:" (assoc person :age 31))
(println "删除:" (dissoc person :city))
(println "合并:" (merge person {:country "USA"}))

;; 4. 集合(Set)：无序不重复
(def colors #{:red :green :blue})
(println "\n=== Set ===")
(println "colors =" colors)
(println "包含红色:" (contains? colors :red))
(println "添加:" (conj colors :yellow))
(println "移除:" (disj colors :green))
(println "交集:" (clojure.set/intersection #{1 2 3} #{2 3 4}))
(println "并集:" (clojure.set/union #{1 2} #{2 3 4}))
(println "差集:" (clojure.set/difference #{1 2 3} #{2 3}))

;; --- 不可变性与结构共享 ---
(println "\n=== 不可变性与结构共享 ===")
(def original [1 2 3 4 5])
(def modified (conj original 6))
(println "原始:" original)    ;; [1 2 3 4 5] — 未被修改
(println "修改后:" modified)   ;; [1 2 3 4 5 6]
;; modified 和 original 共享内部数据节点，没有完整复制

;; --- 函数定义 ---
(println "\n=== 函数定义 ===")

;; defn 定义命名函数
(defn add [a b]
  (+ a b))

;; 多参数列表
(defn greet
  ([name] (str "你好, " name "!"))
  ([name greeting] (str greeting ", " name "!")))

;; 文档字符串
(defn factorial
  "计算阶乘，n必须是非负整数"
  [n]
  (if (<= n 1)
    1
    (* n (factorial (dec n)))))

;; 尾递归版本（使用recur避免栈溢出）
(defn factorial-tail [n]
  (loop [i n acc 1]
    (if (<= i 1)
      acc
      (recur (dec i) (* acc i)))))

(println "add(3,4) =" (add 3 4))
(println "greet(\"World\") =" (greet "World"))
(println "greet(\"World\", \"Hello\") =" (greet "World" "Hello"))
(println "factorial(5) =" (factorial 5))
(println "factorial-tail(5) =" (factorial-tail 5))
(println "factorial-tail(20) =" (factorial-tail 20))

;; 匿名函数
(println "\n=== 匿名函数 ===")
(println ((fn [x] (* x x)) 5))           ;; 完整匿名函数
(println (#(* % %) 5))                   ;; 简写：#() %代表参数
(println (#(+ %1 %2) 3 4))              ;; %1 %2 代表第一二个参数
(println (map #(* % 2) [1 2 3 4 5]))    ;; 配合map使用

;; --- 序列抽象 ---
;; 所有集合都可以用seq操作，统一接口
(println "\n=== 序列抽象 ===")

;; map：对每个元素应用函数
(println "map:" (map inc [1 2 3 4 5]))            ;; (2 3 4 5 6)
(println "map多集合:" (map + [1 2 3] [10 20 30])) ;; (11 22 33)

;; filter：筛选
(println "filter偶数:" (filter even? [1 2 3 4 5 6]))
(println "filter自定义:" (filter #(> % 3) [1 2 3 4 5]))

;; reduce：归约
(println "reduce求和:" (reduce + [1 2 3 4 5]))
(println "reduce带初值:" (reduce + 100 [1 2 3]))
(println "reduce自定义:" (reduce (fn [acc x] (conj acc (* x x))) [] [1 2 3]))

;; 其他常用序列函数
(println "take:" (take 3 (range 10)))         ;; (0 1 2)
(println "drop:" (drop 3 (range 10)))         ;; (3 4 5 6 7 8 9)
(println "partition:" (partition 2 [1 2 3 4 5 6]))  ;; ((1 2) (3 4) (5 6))
(println "interleave:" (interleave [1 2 3] [:a :b :c])) ;; (1 :a 2 :b 3 :c)
(println "concat:" (concat [1 2] [3 4] [5]))  ;; (1 2 3 4 5)
(println "sort:" (sort [3 1 4 1 5 9 2 6]))
(println "distinct:" (distinct [1 1 2 2 3 3 1]))
(println "frequencies:" (frequencies [:a :b :a :c :a :b]))
(println "group-by:" (group-by even? [1 2 3 4 5 6]))
(println "mapcat:" (mapcat (fn [x] [x x]) [1 2 3]))

;; --- 惰性序列 ---
(println "\n=== 惰性序列 ===")

;; range 生成惰性序列（可以无限）
(println "range 5:" (take 5 (range)))        ;; (0 1 2 3 4)
(println "range 10-15:" (range 10 15))       ;; (10 11 12 13 14)

;; iterate：无限迭代
(println "iterate:" (take 5 (iterate inc 0)))    ;; (0 1 2 3 4)
(println "powers of 2:" (take 6 (iterate #(* 2 %) 1))) ;; (1 2 4 8 16 32)

;; 自定义惰性序列：斐波那契
(def fibs (map first (iterate (fn [[a b]] [b (+ a b)]) [0 1])))
(println "fibonacci:" (take 10 fibs))

;; lazy-seq：手动定义惰性序列
(defn natural-nums
  "生成从n开始的自然数序列（无限）"
  [n]
  (lazy-seq
    (cons n (natural-nums (inc n)))))

(println "natural-nums:" (take 5 (natural-nums 1)))

;; --- 线程宏(Thread-first / Thread-last) ---
(println "\n=== 线程宏 ===")

;; -> 线程优先：将前一个结果作为后一个函数的第一个参数
;; 类似Elixir的管道运算符
(def result-thread-first
  (-> 5
      inc          ;; (inc 5) => 6
      (* 2)        ;; (* 6 2) => 12
      (- 3)        ;; (- 12 3) => 9
      str))        ;; (str 9) => "9"
(println "thread-first:" result-thread-first)

;; ->> 线程最后：将前一个结果作为后一个函数的最后一个参数
(def result-thread-last
  (->> [1 2 3 4 5 6 7 8 9 10]
       (filter even?)         ;; (filter even? [1..10]) => (2 4 6 8 10)
       (map #(* % 10))        ;; (map #(* % 10) (2 4 6 8 10)) => (20 40 60 80 100)
       (reduce +)             ;; (reduce + (20 40 60 80 100)) => 300
       (#(* % 2))))           ;; (* 300 2) => 600
(println "thread-last:" result-thread-last)

;; --- let绑定与解构 ---
(println "\n=== let绑定与解构 ===")

;; 基本let
(let [a 10
      b 20
      sum (+ a b)]
  (println "let结果:" sum))

;; 向量解构
(let [[x y z] [1 2 3]]
  (println "向量解构:" x y z))

(let [[first _ third] [10 20 30]]
  (println "跳过元素:" first third))

(let [[a b & rest] [1 2 3 4 5]]
  (println "剩余绑定:" a b rest))

;; Map解构
(let [{:keys [name age]} {:name "Alice" :age 30}]
  (println "Map解构:" name age))

(let [{:keys [name age] :or {age "未知"}} {:name "Bob"}]
  (println "默认值解构:" name age))

;; 嵌套解构
(let [{[x y] :coords :keys [name]} {:name "Point" :coords [3 4]}]
  (println "嵌套解构:" name x y))

;; --- 关键字作为函数 ---
(println "\n=== 关键字作为函数 ===")
(def users [{:name "Alice" :age 30}
            {:name "Bob" :age 25}
            {:name "Carol" :age 35}])

;; :name 作为函数从每个map中提取值
(println "所有名字:" (map :name users))
(println "所有年龄:" (map :age users))

;; 思考题：Clojure的前缀表达式(+ 1 2 3)和中缀表达式1+2+3相比有什么优势？
;;         "代码即数据"(Homoiconicity)对宏系统有什么意义？
;;         持久化数据结构如何在不可变的前提下保证性能？

;; ============================================================
;; 第2题：宏与STM（宏定义 / 软件事务内存）
;; ============================================================
;; 知识点讲解：
;; Clojure的宏系统是Lisp最强大的特性之一。
;; 由于"代码即数据"，宏可以接收代码（作为列表数据），变换后再执行。
;;
;; 宏(Macro)：
;;   - defmacro 定义宏
;;   - 宏在编译期展开，不产生运行时开销
;;   - 宏接收未求值的代码形式(form)，返回新的代码形式
;;   - 反引号(`)用于模板引用，波浪号(~)用于解引用(注入值)
;;   - ~@ 用于展开列表(splicing unquote)
;;
;; STM(Software Transactional Memory)：
;;   - Clojure对共享可变状态的解决方案
;;   - 通过"事务"原子性地修改Ref引用的可变状态
;;   - 类似数据库事务：ACID特性（不含持久性）
;;   - dosync 开启事务
;;   - ref-set 设置值, alter 修改值, commute 协调修改
;;   - 不需要锁，不会死锁，自动重试冲突事务

;; --- 宏基础 ---
(println "=== 宏基础 ===")

;; quote：阻止求值
(println "quote:" '(+ 1 2 3))    ;; (+ 1 2 3) — 不求值，返回列表
(println "eval:" (eval '(+ 1 2 3)))  ;; 6 — 手动求值

;; syntax-quote（反引号`）：命名空间限定的引用
;; unquote（波浪号~）：在引用中注入值
(def macro-var 42)
(println "syntax-quote:" `(1 2 ~macro-var 4))  ;; (1 2 42 4)

;; unquote-splicing（~@）：展开列表
(def splice-list [2 3 4])
(println "unquote-splice:" `(1 ~@splice-list 5))  ;; (1 2 3 4 5)

;; --- 定义简单宏 ---

;; 宏：unless（当条件为假时执行）
(defmacro unless [condition & body]
  `(if (not ~condition)
     (do ~@body)))

(println "\n=== unless宏 ===")
(unless false (println "条件为假，执行了!"))
(unless true (println "这不会执行"))

;; 宏：when-let的变体
(defmacro when-some [binding & body]
  (let [[sym expr] binding]
    `(let [tmp# ~expr]
       (when (some? tmp#)
         (let [~sym tmp#]
           ~@body)))))

(println "\n=== when-some宏 ===")
(when-some [x (if true 42 nil)]
  (println "x有值:" x))

;; 宏：计时执行
(defmacro time-it [expr]
  `(let [start# (System/nanoTime)
         result# ~expr
         end# (System/nanoTime)]
     (println (str "执行耗时: " (/ (double (- end# start#)) 1000000.0) " ms"))
     result#))

(println "\n=== time-it宏 ===")
(time-it (reduce + (range 100000)))

;; 宏：交换两个变量
(defmacro swap! [a b]
  `(let [tmp# ~a]
     (set! ~a ~b)
     (set! ~b tmp#)))

;; 宏：管道运算符（模拟Elixir的|>）
(defmacro |> [val & forms]
  (loop [expr val
         forms forms]
    (if (empty? forms)
      expr
      (let [form (first forms)]
        (recur (if (list? form)
                 `(~(first form) ~expr ~@(rest form))
                 (list form expr))
               (rest forms))))))

(println "\n=== |> 管道宏 ===")
(println "管道结果:"
  (|> 5
      inc
      (* 2)
      (- 3)))   ;; ((- (* (inc 5) 2)) 3) = 9

;; --- 宏展开检查 ---
(println "\n=== 宏展开检查 ===")

;; macroexpand 展开宏
(println "unless展开:")
(println (macroexpand '(unless false (println "hi"))))

(println "\ntime-it展开:")
(println (macroexpand '(time-it (+ 1 2))))

;; --- 代码生成宏 ---
(println "\n=== 代码生成宏 ===")

;; 宏：为多个字段生成getter函数
(defmacro defgetters [type-name & fields]
  (let [getter-names (map #(symbol (str type-name "-" (name %))) fields)]
    `(do
       ~@(for [[fname field] (map vector getter-names fields)]
           `(defn ~fname [~'obj] (~field ~'obj))))))

;; 使用宏批量生成getter
(defgetters user :name :age :email)

;; 现在可以使用 user-name, user-age, user-email
(println "生成的getter:")
(println "name:" (user-name {:name "Alice" :age 30 :email "a@b.com"}))
(println "age:" (user-age {:name "Alice" :age 30 :email "a@b.com"}))
(println "email:" (user-email {:name "Alice" :age 30 :email "a@b.com"}))

;; --- STM：软件事务内存 ---
(println "\n=== STM 软件事务内存 ===")

;; 创建Ref（事务引用）
(def account-a (ref 1000))
(def account-b (ref 500))

(println "初始状态:")
(println "  账户A:" @account-a)  ;; @ 用于解引用(deref)
(println "  账户B:" @account-b)

;; 转账函数：在事务中原子性地修改两个Ref
(defn transfer [from-ref to-ref amount]
  (dosync
    (alter from-ref - amount)
    (alter to-ref + amount)))

;; 执行转账
(transfer account-a account-b 200)

(println "\n转账200后:")
(println "  账户A:" @account-a)  ;; 800
(println "  账户B:" @account-b)  ;; 700

;; --- STM并发安全性 ---
(println "\n=== STM并发安全性 ===")

(def counter (ref 0))

;; 使用pmap（并行map）并发增加计数器
;; STM自动处理冲突，重试事务
(doall (pmap (fn [_]
              (dosync
                (alter counter inc)))
            (range 1000)))

(println "并发1000次递增后:" @counter)  ;; 1000

;; --- commute vs alter ---
;; alter：事务提交时如果值被改了，重试整个事务
;; commute：事务提交时用最新值重新计算（不会重试，适合交换律操作）
(println "\n=== commute vs alter ===")

(def stats (ref {:count 0 :total 0}))

;; alter：严格顺序，冲突时重试
(defn add-strict [n]
  (dosync
    (alter stats update :count inc)
    (alter stats update :total + n)))

;; commute：适用于交换律操作，不重试
(defn add-commute [n]
  (dosync
    (commute stats update :count inc)
    (commute stats update :total + n)))

(dosync (ref-set stats {:count 0 :total 0}))
(add-strict 10)
(add-strict 20)
(println "alter结果:" @stats)

(dosync (ref-set stats {:count 0 :total 0}))
(add-commute 10)
(add-commute 20)
(println "commute结果:" @stats)

;; --- ref-set：直接设置值 ---
(println "\n=== ref-set ===")
(dosync
  (ref-set account-a 2000)
  (ref-set account-b 1000))
(println "重设后: A=" @account-a ", B=" @account-b)

;; --- Atom：轻量级原子引用 ---
;; Atom比Ref更简单，适合单一可变值，不需要事务组合
(println "\n=== Atom 原子引用 ===")

(def state (atom {:count 0 :items []}))

;; swap! 修改atom的值（函数式更新）
(swap! state update :count inc)
(swap! state update :items conj "item1")
(swap! state update :items conj "item2")
(swap! state update :count inc)

(println "Atom状态:" @state)

;; compare-and-set!：CAS操作
(def cas-result (compare-and-set! state @state (assoc @state :count 100)))
(println "CAS成功?" cas-result)
(println "CAS后:" @state)

;; reset!：直接重设
(reset! state {:count 0 :items []})
(println "reset后:" @state)

;; --- volatile：最低开销的可变引用 ---
;; 不保证可见性，仅用于单线程内的性能优化
(println "\n=== volatile ===")
(def v (volatile! 0))
(vreset! v 42)
(println "volatile值:" (vget v))

;; --- Agent：异步更新的引用 ---
(println "\n=== Agent ===")

(def async-counter (agent 0))

;; send 异步更新agent的值
(send async-counter inc)
(send async-counter inc)
(send async-counter + 10)

;; 等待agent完成（需要一点时间）
(Thread/sleep 100)
(println "Agent值:" @async-counter)

;; --- STM与锁的对比 ---
(println "\n=== STM vs 锁 对比 ===")
(println "
  传统锁模式：
  - 需要手动加锁/解锁
  - 容易死锁
  - 难以组合（锁的顺序问题）
  - 持有锁时不能执行耗时操作

  Clojure STM模式：
  - 事务自动管理（dosync）
  - 不会死锁（冲突时重试而非等待）
  - 可组合（多个ref在同一个事务中）
  - 乐观并发：先执行，提交时检查冲突
  - 缺点：冲突频繁时重试开销大
")

;; --- 实战：用STM实现银行系统 ---
(println "=== STM实战：银行系统 ===")

(def accounts
  {:alice (ref 5000)
   :bob   (ref 3000)
   :carol (ref 2000)})

(defn bank-transfer [from-key to-key amount]
  (dosync
    (let [from-ref (from-key accounts)
          to-ref   (to-key accounts)
          balance  @from-ref]
      (if (>= balance amount)
        (do
          (alter from-ref - amount)
          (alter to-ref + amount)
          {:status :success :amount amount})
        {:status :failed :reason :insufficient-funds}))))

(defn print-balances []
  (doseq [[name ref-acc] accounts]
    (println (format "  %s: %d" (name {:alice "Alice" :bob "Bob" :carol "Carol"}) @ref-acc))))

(println "初始余额:")
(print-balances)

(println "\nAlice -> Bob 转账 1000:")
(println "  结果:" (bank-transfer :alice :bob 1000))
(print-balances)

(println "\nBob -> Carol 转账 500:")
(println "  结果:" (bank-transfer :bob :carol 500))
(print-balances)

(println "\nCarol -> Alice 转账 99999 (余额不足):")
(println "  结果:" (bank-transfer :carol :alice 99999))
(print-balances)

;; 思考题：Clojure的宏和普通函数有什么本质区别？
;;         什么时候应该用宏，什么时候应该用函数？
;;         STM和传统锁机制相比有什么优势和劣势？
;;         Ref、Atom、Agent三种可变引用分别适用于什么场景？
