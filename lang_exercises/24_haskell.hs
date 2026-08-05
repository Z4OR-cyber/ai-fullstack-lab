-- ============================================================
-- 阶段：函数式编程语言 - Haskell语言练习
-- 题数：5题
-- 创建日期：2026-08-05
-- ============================================================

-- ============================================================
-- 第1题：Haskell基础（函数 / 类型 / 列表推导）
-- ============================================================
-- 知识点讲解：
-- Haskell是纯函数式编程语言，核心特征：
--   - 纯函数：没有副作用，相同输入永远产生相同输出
--   - 不可变数据：数据创建后不可修改
--   - 惰性求值：只在需要时计算，支持无限数据结构
--   - 强类型系统：编译期类型检查，支持类型推断
-- 基本语法要点：
--   - 函数定义：函数名 参数 = 函数体
--   - 类型签名：函数名 :: 类型1 -> 类型2 -> 返回类型
--   - 列表：[a] 表示元素类型为a的列表
--   - 元组：(a, b) 表示二元组
--   -- 单行注释用 --，多行用 {- ... -}

module HaskellExercises where

-- --- 基本函数定义 ---

-- 带类型签名的函数
add :: Int -> Int -> Int
add x y = x + y

-- 类型推断（不写签名也能推断）
multiply x y = x * y

-- 守卫表达式(Guard)：条件分支
classify :: Int -> String
classify n
  | n < 0     = "负数"
  | n == 0    = "零"
  | n < 10    = "个位数"
  | n < 100   = "两位数"
  | otherwise = "大数"

-- 模式匹配：按参数结构分支
factorial :: Integer -> Integer
factorial 0 = 1
factorial n = n * factorial (n - 1)

-- 列表模式匹配
myLength :: [a] -> Int
myLength []     = 0
myLength (_:xs) = 1 + myLength xs

-- where子句：局部定义
pythagoreanTriples :: Int -> [(Int, Int, Int)]
pythagoreanTriples n = [(a, b, c) | a <- [1..n], b <- [a..n], c <- [b..n], a^2 + b^2 == c^2]

-- --- 列表推导式 ---
-- 类似数学集合表示法：[表达式 | 生成器, 条件]

-- 生成平方数列表
squares :: Int -> [Int]
squares n = [x^2 | x <- [1..n]]

-- 带条件的列表推导
evens :: [Int] -> [Int]
evens xs = [x | x <- xs, x `mod` 2 == 0]

-- 多生成器：笛卡尔积
pairs :: [a] -> [b] -> [(a, b)]
pairs xs ys = [(x, y) | x <- xs, y <- ys]

-- 嵌套列表推导：展平矩阵
flatten :: [[a]] -> [a]
flatten xss = [x | xs <- xss, x <- xs]

-- --- 元组操作 ---
-- 计算列表中每个元素及其平方的元组
withSquares :: [Int] -> [(Int, Int)]
withSquares xs = [(x, x^2) | x <- xs]

-- 从元组列表中提取第一个元素
firsts :: [(a, b)] -> [a]
firsts pairs = [x | (x, _) <- pairs]

-- --- let ... in 表达式 ---
circleArea :: Double -> Double
circleArea r =
  let pi' = 3.14159265358979
      r2  = r * r
  in pi' * r2

-- --- 函数组合与管道 ---
-- Haskell函数是右结合的：f g x = f (g x)
-- (.) 是函数组合运算符
composeExample :: [Int] -> Int
composeExample = sum . map (*2) . filter even

-- --- 匿名函数(lambda) ---
-- \参数 -> 函数体
addOneToList :: [Int] -> [Int]
addOneToList = map (\x -> x + 1)

-- --- 部分应用 ---
-- Haskell函数默认是柯里化的，可以部分应用
add5 :: Int -> Int
add5 = add 5

multiplyBy3 :: Int -> Int
multiplyBy3 = multiply 3

-- --- 简单递归：快速排序 ---
quickSort :: Ord a => [a] -> [a]
quickSort [] = []
quickSort (p:xs) =
  quickSort [x | x <- xs, x < p]
  ++ [p]
  ++ quickSort [x | x <- xs, x >= p]

-- 测试用例（在GHCi中执行）
-- >>> add 3 4
-- 7
-- >>> classify (-5)
-- "负数"
-- >>> factorial 5
-- 120
-- >>> squares 5
-- [1,4,9,16,25]
-- >>> quickSort [3,1,4,1,5,9,2,6]
-- [1,1,2,3,4,5,6,9]

-- 思考题：Haskell的函数为什么默认是"柯里化"的？
--         这对部分应用和函数组合有什么好处？
--         模式匹配和守卫表达式各自适用于什么场景？

-- ============================================================
-- 第2题：类型类（Eq / Ord / Show / Functor）
-- ============================================================
-- 知识点讲解：
-- Haskell的类型类(Typeclass)类似于接口(Interface)，定义了一组行为。
-- 一个类型如果实现了某类型类的方法，就"属于"该类型类。
-- 常见类型类：
--   - Eq：支持相等判断 (==, /=)
--   - Ord：支持大小比较 (<, >, compare)
--   - Show：可转换为字符串 (show)
--   - Read：可从字符串解析 (read)
--   - Num：支持数值运算 (+, -, *)
--   - Enum：可枚举（用于区间 [1..10]）
--   - Functor：支持映射操作 (fmap / <$>)
--   - Applicative：支持在上下文中应用函数 (<*>)
--   - Monad：支持顺序计算 (>>=)

-- --- 自定义类型 ---
data Color = Red | Green | Blue | Yellow | Purple
  deriving (Eq, Ord, Show, Enum, Bounded)

-- deriving 自动派生类型类实例
-- Haskell编译器会自动为 Color 生成 ==, <, show 等实现

-- 测试
-- >>> Red == Red
-- True
-- >>> Red < Blue
-- True
-- >>> show Green
-- "Green"
-- >>> [Red .. Blue]
-- [Red,Green,Blue]

-- --- 手动实现类型类实例 ---
data Temperature = Celsius Double | Fahrenheit Double

-- 手动实现 Show
instance Show Temperature where
  show (Celsius c)    = show c ++ "°C"
  show (Fahrenheit f) = show f ++ "°F"

-- 手动实现 Eq
instance Eq Temperature where
  (Celsius c) == (Fahrenheit f)       = c == (f - 32) * 5 / 9
  (Fahrenheit f) == (Celsius c)       = (f - 32) * 5 / 9 == c
  (Celsius c1) == (Celsius c2)        = c1 == c2
  (Fahrenheit f1) == (Fahrenheit f2)  = f1 == f2

-- 手动实现 Ord
instance Ord Temperature where
  compare (Celsius c1) (Celsius c2)        = compare c1 c2
  compare (Celsius c) (Fahrenheit f)       = compare c ((f - 32) * 5 / 9)
  compare (Fahrenheit f) (Celsius c)       = compare ((f - 32) * 5 / 9) c
  compare (Fahrenheit f1) (Fahrenheit f2)  = compare f1 f2

-- 转换函数
toCelsius :: Temperature -> Temperature
toCelsius (Celsius c)    = Celsius c
toCelsius (Fahrenheit f) = Celsius ((f - 32) * 5 / 9)

toFahrenheit :: Temperature -> Temperature
toFahrenheit (Celsius c)    = Fahrenheit (c * 9 / 5 + 32)
toFahrenheit (Fahrenheit f) = Fahrenheit f

-- >>> show (Celsius 25)
-- "25.0°C"
-- >>> show (toFahrenheit (Celsius 100))
-- "212.0°F"

-- --- 参数化类型（泛型）---
data Box a = Box a
  deriving (Show)

-- 为 Box 实现 Functor
instance Functor Box where
  fmap f (Box x) = Box (f x)

-- 使用
-- >>> fmap (+1) (Box 41)
-- Box 42
-- >>> (*2) <$> Box 21
-- Box 42

-- --- Maybe类型：安全处理可能失败的计算 ---
safeDivide :: Double -> Double -> Maybe Double
safeDivide _ 0 = Nothing
safeDivide x y = Just (x / y)

-- 使用 Functor 处理 Maybe
-- >>> fmap (+10) (safeDivide 10 2)
-- Just 15.0
-- >>> fmap (+10) (safeDivide 10 0)
-- Nothing

-- --- Either类型：带错误信息的计算 ---
safeDivideE :: Double -> Double -> Either String Double
safeDivideE _ 0 = Left "除零错误"
safeDivideE x y = Right (x / y)

-- --- 自定义类型类 ---
-- 定义一个描述"可测量"的类型类
class Measurable a where
  measure :: a -> Double
  unit :: a -> String

-- 为不同类型实现
instance Measurable Double where
  measure = id
  unit _ = "m"

instance Measurable Temperature where
  measure (Celsius c)    = c
  measure (Fahrenheit f) = (f - 32) * 5 / 9
  unit _ = "°C"

-- --- 类型约束 ---
-- 函数签名中的类型约束
maximumOf :: Ord a => [a] -> a
maximumOf []     = error "空列表没有最大值"
maximumOf [x]    = x
maximumOf (x:xs) = max x (maximumOf xs)

-- 多类型约束
showAndCompare :: (Show a, Ord a) => a -> a -> String
showAndCompare a b =
  case compare a b of
    LT -> show a ++ " < " ++ show b
    EQ -> show a ++ " == " ++ show b
    GT -> show a ++ " > " ++ show b

-- --- newtype：零开销类型包装 ---
newtype Score = Score Int
  deriving (Show, Eq)

instance Ord Score where
  compare (Score a) (Score b) = compare b a  -- 反转：分数越高排越前

-- >>> Score 90 > Score 85
-- True

-- 思考题：类型类(Typeclass)和OOP中的接口(Interface)有什么本质区别？
--         Haskell的类型类是如何实现"特设多态"(Ad-hoc Polymorphism)的？
--         newtype 和 data 的区别是什么？为什么 newtype 是零开销的？

-- ============================================================
-- 第3题：单子（Monad / IO Monad / Maybe / Either）
-- ============================================================
-- 知识点讲解：
-- Monad(单子)是Haskell中最重要也最被误解的概念。
-- 简单理解：Monad是一种"上下文包装器"，提供了一种在"有上下文的计算"
-- 之间串联的方式，而不需要手动解包。
--
-- Monad的核心操作：
--   - return（或pure）：将普通值包装进Monad
--   - >>=（bind）：将Monad中的值取出，传递给下一个返回Monad的函数
--
-- 常见Monad：
--   - IO Monad：封装副作用（输入输出），保持纯函数性
--   - Maybe Monad：封装"可能失败"的计算
--   - Either Monad：封装"可能出错"的计算，带错误信息
--   - List Monad：封装"非确定性计算"（多结果）
--   - State Monad：封装"有状态"的计算
--
-- do语法糖：do块会被编译器脱糖为 >>= 链式调用

-- --- Maybe Monad ---

-- 链式安全计算：不用Monad的写法（嵌套if很丑）
unsafeChain :: Double -> Double -> Double -> Maybe Double
unsafeChain a b c =
  case safeDivide a b of
    Nothing -> Nothing
    Just r1 -> case safeDivide r1 c of
      Nothing -> Nothing
      Just r2 -> Just (r2 + 1)

-- 用Monad的 >>= 写法（简洁）
monadChain :: Double -> Double -> Double -> Maybe Double
monadChain a b c =
  safeDivide a b >>= \r1 ->
  safeDivide r1 c >>= \r2 ->
  Just (r2 + 1)

-- 用 do 语法糖（最清晰）
doChain :: Double -> Double -> Double -> Maybe Double
doChain a b c = do
  r1 <- safeDivide a b   -- 从Maybe中取值，失败则短路返回Nothing
  r2 <- safeDivide r1 c  -- 同上
  return (r2 + 1)         -- 将结果包装回Maybe

-- >>> doChain 100 5 2
-- Just 11.0
-- >>> doChain 100 0 2
-- Nothing

-- --- Either Monad ---
-- Either提供了更丰富的错误信息
divideChain :: Double -> Double -> Double -> Either String Double
divideChain a b c = do
  r1 <- safeDivideE a b
  r2 <- safeDivideE r1 c
  return (r2 * 100)

-- >>> divideChain 100 5 2
-- Right 1000.0
-- >>> divideChain 100 0 2
-- Left "除零错误"

-- --- List Monad ---
-- 列表也是Monad，表示"非确定性计算"
-- 每个 >>= 会产生多个结果
listComputation :: [Int]
listComputation = do
  x <- [1, 2, 3]       -- 从列表中取每个值
  y <- [10, 20]        -- 对每个x，再取每个y
  return (x + y)        -- 组合结果

-- 等价于：[x + y | x <- [1,2,3], y <- [10,20]]
-- 结果：[11,21,12,22,13,23]

-- --- IO Monad ---
-- Haskell中所有副作用都必须在IO Monad中进行
-- main函数是程序的入口，类型为 IO ()

main :: IO ()
main = do
  putStrLn "=== Haskell IO Monad 演示 ==="

  -- 基本输出
  putStrLn "请输入你的名字："

  -- 基本输入
  name <- getLine

  -- 字符串拼接输出
  putStrLn ("你好, " ++ name ++ "!")

  -- 在IO中使用纯函数
  let nums = [1..5]
  putStrLn ("1到5的平方: " ++ show (squares 5))

  -- 读取文件（IO操作）
  -- content <- readFile "input.txt"
  -- putStrLn content

  -- 写入文件
  -- writeFile "output.txt" "Hello from Haskell!"

  putStrLn "程序结束"

-- --- 自定义Monad ---
-- 定义一个带日志记录的Monad
data WriterLog a = WriterLog a [String]
  deriving (Show)

-- 实现Functor
instance Functor WriterLog where
  fmap f (WriterLog a logs) = WriterLog (f a) logs

-- 实现Applicative
instance Applicative WriterLog where
  pure a = WriterLog a []
  (WriterLog f logs1) <*> (WriterLog a logs2) = WriterLog (f a) (logs1 ++ logs2)

-- 实现Monad
instance Monad WriterLog where
  return = pure
  (WriterLog a logs) >>= f =
    let (WriterLog b newLogs) = f a
    in WriterLog b (logs ++ newLogs)

-- 使用Writer Monad记录计算日志
computeWithLog :: WriterLog Int
computeWithLog = do
  let step1 = 10
  WriterLog step1 ["步骤1: 初始值 = 10"]

  let step2 = step1 * 3
  WriterLog step2 ["步骤2: 乘以3 = 30"]

  let step3 = step2 + 12
  WriterLog step3 ["步骤3: 加12 = 42"]

  return step3

-- >>> computeWithLog
-- WriterLog 42 ["步骤1: 初始值 = 10","步骤2: 乘以3 = 30","步骤3: 加12 = 42"]

-- --- Monad法则 ---
-- 1. 左单位元：return x >>= f ≡ f x
-- 2. 右单位元：m >>= return ≡ m
-- 3. 结合律：(m >>= f) >>= g ≡ m >>= (\x -> f x >>= g)

-- 验证Maybe的左单位元法则
-- return 5 >>= (\x -> Just (x * 2))  ==  Just 10
-- (\x -> Just (x * 2)) 5             ==  Just 10  ✓

-- 思考题：Monad的 >>= 操作本质上做了什么？
--         为什么Haskell要用IO Monad来隔离副作用，而不是像其他语言那样允许全局可变状态？
--         do语法糖和 >>= 链式调用是等价的吗？

-- ============================================================
-- 第4题：惰性求值（无限列表 / Thunk）
-- ============================================================
-- 知识点讲解：
-- Haskell默认使用惰性求值(Lazy Evaluation)：
--   - 表达式只在"需要"其结果时才被计算
--   - 未使用的部分永远不会被计算
--   - 这使得无限数据结构成为可能
-- Thunk：惰性求值的内部实现，是一个"待计算的延迟表达式"
--   - 当值被需要时，Thunk被"强制求值"(force)
--   - 求值后结果被缓存（只计算一次）
-- 优势：支持无限结构、避免不必要计算、模块化编程
-- 劣势：内存占用不可预测、性能难以分析、可能产生空间泄漏

-- --- 无限列表 ---
-- Haskell可以定义无限列表，因为只有需要的部分会被计算
ones :: [Integer]
ones = 1 : ones  -- 无限的1

-- take 从无限列表中取有限个
-- >>> take 5 ones
-- [1,1,1,1,1]

-- 自然数序列
naturals :: [Integer]
naturals = [0..]

-- >>> take 10 naturals
-- [0,1,2,3,4,5,6,7,8,9]

--- 斐波那契数列（无限）
fibs :: [Integer]
fibs = 0 : 1 : zipWith (+) fibs (tail fibs)

-- >>> take 10 fibs
-- [0,1,1,2,3,5,8,13,21,34]

-- --- 惰性求值避免不必要的计算 ---
-- 条件表达式中不需要的分支不会被计算
safeHead :: [a] -> Maybe a
safeHead []    = Nothing
safeHead (x:_) = Just x

-- 以下表达式中，error永远不会被触发（因为条件为True）
-- >>> safeHead [1..]
-- Just 1

-- --- 无限素数序列 ---
-- 使用筛法生成无限素数
primes :: [Integer]
primes = sieve [2..]
  where
    sieve (p:xs) = p : sieve [x | x <- xs, x `mod` p /= 0]

-- >>> take 10 primes
-- [2,3,5,7,11,13,17,19,23,29]

-- --- 延迟计算与seq ---
-- Haskell提供了 seq 函数来强制求值
-- seq :: a -> b -> b
-- 用法：x `seq` y  先求值x，再返回y

-- 使用 $! 强制求值参数
strictIdentity :: a -> a
strictIdentity x = x `seq` x

--- 深度强制求值：deepseq（需要 import Control.DeepSeq）
-- import Control.DeepSeq (deepseq, NFData)

-- --- 交互式生成器 ---
-- 生成柯拉兹序列（3n+1问题）
collatz :: Integer -> [Integer]
collatz 1 = [1]
collatz n
  | even n    = n : collatz (n `div` 2)
  | otherwise = n : collatz (3 * n + 1)

-- >>> collatz 27
-- [27,82,41,124,62,31,94,47,142,71,214,107,322,161,484,242,121,364,182,91,274,137,412,206,103,310,155,466,233,700,350,175,526,263,790,395,1186,593,1780,890,445,1336,668,334,167,502,251,754,377,1132,566,283,850,425,1276,638,319,958,479,1438,719,2158,1079,3238,1619,4858,2429,7288,3644,1822,911,2734,1367,4102,2051,6154,3077,9232,4616,2308,1154,577,1732,866,433,1300,650,325,976,488,244,122,61,184,92,46,23,70,35,106,53,160,80,40,20,10,5,16,8,4,2,1]

-- --- foldr与惰性求值 ---
-- foldr 可以在无限列表上工作（因为它是惰性的）
-- foldr (+) 0 [1..]  -- 这会无限循环（需要遍历整个列表）
-- 但 foldr 可以与惰性函数配合：
-- >>> take 5 (map (*2) [1..])
-- [2,4,6,8,10]

-- 无限列表的takeWhile
-- >>> takeWhile (< 100) [n^2 | n <- [1..]]
-- [1,4,9,16,25,36,49,64,81]

-- --- 空间泄漏示例 ---
-- 以下代码可能导致空间泄漏（累积大量Thunk）
-- sum' [1..1000000]  -- foldl会累积Thunk

-- 严格fold：避免空间泄漏
-- foldl' :: (b -> a -> b) -> b -> [a] -> b
-- import Data.List (foldl')

-- --- 无限数据结构：博弈树 ---
-- 定义一个简单的博弈树
data GameTree a = Node a [GameTree a]
  deriving (Show)

-- 无限展开的树
iterateTree :: (a -> [a]) -> a -> GameTree a
iterateTree f x = Node x (map (iterateTree f) (f x))

-- 只取有限深度
takeDepth :: Int -> GameTree a -> GameTree a
takeDepth 0 (Node x _)   = Node x []
takeDepth n (Node x children) = Node x (map (takeDepth (n-1)) children)

-- --- 惰性求值与性能 ---
-- 惰性求值有时会产生"空间泄漏"(Space Leak)
-- 使用严格模式或 bang pattern 来控制求值策略

-- 普通版（可能空间泄漏）
sumLazy :: [Int] -> Int
sumLazy = foldr (+) 0

-- 严格版（使用 bang pattern）
{-# LANGUAGE BangPatterns #-}
sumStrict :: [Int] -> Int
sumStrict = go 0
  where
    go !acc []     = acc
    go !acc (x:xs) = go (acc + x) xs

-- 思考题：为什么 fibs = 0 : 1 : zipWith (+) fibs (tail fibs) 能正确工作？
--         它是如何"自引用"的？惰性求值在这里起到了什么关键作用？
--         什么是"空间泄漏"？如何用 bang pattern 避免它？

-- ============================================================
-- 第5题：函数式模式（折叠 / 映射 / 柯里化 / 组合）
-- ============================================================
-- 知识点讲解：
-- 函数式编程的核心模式：
--   - map：对每个元素应用函数
--   - filter：按条件筛选
--   - fold（reduce）：将列表归约为单个值
--     - foldr：从右向左折叠（可处理无限列表）
--     - foldl：从左向右折叠（尾递归）
--   - 柯里化(Currying)：多参数函数转化为单参数函数链
--   - 函数组合(.)：将多个函数串联
--   - 应用函子(Applicative)：在上下文中应用函数
-- 这些模式是函数式编程的"积木"，可以组合出复杂逻辑。

-- --- map：映射 ---
-- 标准库已提供 map，这里手动实现
myMap :: (a -> b) -> [a] -> [b]
myMap _ []     = []
myMap f (x:xs) = f x : myMap f xs

-- --- filter：筛选 ---
myFilter :: (a -> Bool) -> [a] -> [a]
myFilter _ []     = []
myFilter p (x:xs)
  | p x       = x : myFilter p xs
  | otherwise = myFilter p xs

-- --- foldr：右折叠 ---
-- foldr f initial [a, b, c] = f a (f b (f c initial))
myFoldr :: (a -> b -> b) -> b -> [a] -> b
myFoldr _ acc []     = acc
myFoldr f acc (x:xs) = f x (myFoldr f acc xs)

-- --- foldl：左折叠 ---
-- foldl f initial [a, b, c] = f (f (f initial a) b) c
myFoldl :: (b -> a -> b) -> b -> [a] -> b
myFoldl _ acc []     = acc
myFoldl f acc (x:xs) = myFoldl f (f acc x) xs

-- --- 用fold实现其他函数 ---

-- 用foldr实现map
mapViaFoldr :: (a -> b) -> [a] -> [b]
mapViaFoldr f = foldr (\x acc -> f x : acc) []

-- 用foldr实现filter
filterViaFoldr :: (a -> Bool) -> [a] -> [a]
filterViaFoldr p = foldr (\x acc -> if p x then x : acc else acc) []

-- 用foldl实现length
lengthViaFoldl :: [a] -> Int
lengthViaFoldl = foldl (\acc _ -> acc + 1) 0

-- 用foldr实现reverse
reverseViaFoldr :: [a] -> [a]
reverseViaFoldr = foldr (\x acc -> acc ++ [x]) []

-- 用foldl实现reverse（更高效）
reverseViaFoldl :: [a] -> [a]
reverseViaFoldl = foldl (flip (:)) []

-- --- 柯里化 ---
-- Haskell所有函数默认柯里化：a -> b -> c 实际是 a -> (b -> c)
-- 即接受a返回一个接受b的函数

-- 柯里化函数
addThree :: Int -> Int -> Int -> Int
addThree x y z = x + y + z

-- 部分应用
addTen :: Int -> Int -> Int
addTen = addThree 10

addTenAndFive :: Int -> Int
addTenAndFive = addThree 10 5

-- >>> addTenAndFive 3
-- 18

-- --- 函数组合 ---
-- (.) :: (b -> c) -> (a -> b) -> a -> c
-- f . g = \x -> f (g x)

-- 组合多个函数
processNumbers :: [Int] -> Int
processNumbers = sum . map (*2) . filter even . take 10

-- 等价的展开形式：
-- processNumbers xs = sum (map (*2) (filter even (take 10 xs)))

-- 使用 & 管道运算符（需要 import Data.Function）
-- import Data.Function ((&))
-- processPipeline :: [Int] -> Int
-- processPipeline xs = xs
--   & take 10
--   & filter even
--   & map (*2)
--   & sum

-- --- 应用函子(Applicative) ---
-- <$> = fmap，<*> 在上下文中应用函数
-- Maybe的Applicative用法
addMaybe :: Maybe Int -> Maybe Int -> Maybe Int
addMaybe a b = (+) <$> a <*> b

-- >>> addMaybe (Just 3) (Just 4)
-- Just 7
-- >>> addMaybe (Just 3) Nothing
-- Nothing

-- 列表的Applicative用法（笛卡尔积）
cartesianAdd :: [Int] -> [Int] -> [Int]
cartesianAdd xs ys = (+) <$> xs <*> ys

-- >>> cartesianAdd [1,2] [10,20,30]
-- [11,21,31,12,22,32]

-- --- 常用高阶函数 ---

-- zipWith：并行对两个列表应用函数
-- >>> zipWith (+) [1,2,3] [10,20,30]
-- [11,22,33]

-- zip：将两个列表配对
-- >>> zip [1,2,3] ['a','b','c']
-- [(1,'a'),(2,'b'),(3,'c')]

-- concatMap：映射后展平
flattenWords :: [String] -> [Char]
flattenWords = concatMap id

-- >>> flattenWords ["hello","world"]
-- "helloworld"

-- unfoldr：fold的逆操作，从种子生成列表
-- import Data.List (unfoldr)
-- >>> unfoldr (\b -> if b == 0 then Nothing else Just (b, b-1)) 5
-- [5,4,3,2,1]

-- --- 实战：函数式数据处理管道 ---
-- 模拟数据处理：筛选、变换、聚合

data Person = Person
  { personName :: String
  , personAge  :: Int
  , personCity :: String
  } deriving (Show)

people :: [Person]
people =
  [ Person "Alice" 30 "NYC"
  , Person "Bob" 25 "LA"
  , Person "Carol" 35 "NYC"
  , Person "Dave" 28 "LA"
  , Person "Eve" 32 "NYC"
  ]

-- 查询：NYC的平均年龄
avgAgeNYC :: Double
avgAgeNYC =
  (fromIntegral . sum $ ages) / (fromIntegral . length $ ages)
  where
    ages = map personAge
         $ filter ((== "NYC") . personCity) people

-- 用函数组合写更简洁
avgAgeNYC' :: Double
avgAgeNYC' =
  let ages = map personAge . filter ((== "NYC") . personCity) $ people
      total = sum ages
      count = length ages
  in fromIntegral total / fromIntegral count

-- --- 递归模式 ---
-- 树的折叠
data Tree a = Leaf a | Branch (Tree a) (Tree a) deriving (Show)

-- 树的fold
foldTree :: (a -> b) -> (b -> b -> b) -> Tree a -> b
foldTree leafF _ (Leaf x)       = leafF x
foldTree leafF branchF (Branch l r) =
  branchF (foldTree leafF branchF l) (foldTree leafF branchF r)

-- 计算树的深度
treeDepth :: Tree a -> Int
treeDepth = foldTree (const 1) (\l r -> 1 + max l r)

-- 树的元素列表
treeToList :: Tree a -> [a]
treeToList = foldTree (:[]) (++)

-- 构建示例树
sampleTree :: Tree Int
sampleTree = Branch (Branch (Leaf 1) (Leaf 2)) (Branch (Leaf 3) (Leaf 4))

-- >>> treeDepth sampleTree
-- 3
-- >>> treeToList sampleTree
-- [1,2,3,4]

-- 思考题：foldr和foldl有什么区别？为什么foldr可以处理无限列表而foldl不能？
--         柯里化(Currying)和部分应用(Partial Application)是同一个概念吗？
--         函数组合 (.) 如何帮助实现"声明式"编程风格？
