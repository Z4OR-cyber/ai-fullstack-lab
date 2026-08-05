# ==============================================================================
# 阶段：Ruby 编程练习
# 题数：5
# 创建日期：2026-08-05
# 说明：由浅入深，覆盖 Ruby 核心特性——从基础语法到元编程与 DSL 构建
# ==============================================================================

# ==============================================================================
# 第 1 题：Ruby 基础（变量 / 符号 / 哈希 / 块）
# ==============================================================================
# 知识点：
#   1. Ruby 中局部变量以小写字母或下划线开头，无需声明类型，动态类型语言。
#   2. 符号（Symbol）是不可变的、内部用整数表示的"轻量字符串"，常用作哈希的键。
#      符号在整个程序中唯一（同一符号只分配一次内存），而字符串每次都新建对象。
#   3. 哈希（Hash）是键值对集合，Ruby 1.9+ 支持简洁的字面量语法 { key: value }。
#   4. 块（Block）是 Ruby 最具特色的特性：一段可以被方法通过 yield 调用的匿名代码。
#      块有两种写法：{ |参数| 代码 } 和 do |参数| ... end（多行时推荐后者）。
# ==============================================================================

# --- 变量与类型 ---
name = "Ruby"           # 局部变量，动态类型
version = 3.2           # 浮点数
year = 2026             # 整数
is_fun = true           # 布尔值

puts "语言：#{name}，版本：#{version}，年份：#{year}，有趣：#{is_fun}"

# --- 符号 vs 字符串 ---
str_a = "hello"
str_b = "hello"
puts str_a.equal?(str_b)  # false —— 每个字符串字面量都是新对象

sym_a = :hello
sym_b = :hello
puts sym_a.equal?(sym_b)  # true  —— 同名符号全局唯一

# --- 哈希 ---
# Ruby 1.9+ 简洁语法：key: value 等价于 :key => value
person = {
  name: "Alice",
  age: 30,
  role: :admin          # 值也可以是符号
}

# 遍历哈希
person.each do |key, value|
  puts "#{key} => #{value}"
end

# 访问与修改
puts person[:name]       # Alice
person[:age] = 31        # 修改值
person[:city] = "Beijing" # 新增键
puts person.inspect

# --- 块的基础用法 ---
# 定义一个接收块的方法
def repeat(n)
  n.times { |i| yield(i) }  # yield 把控制权交给块，并传参
end

# 传入块
repeat(3) do |index|
  puts "第 #{index + 1} 次执行块"
end

# 块也可以用花括号写法（单行场景）
repeat(2) { |i| puts "简写块：#{i}" }

# 思考题：符号和字符串在哈希键场景下各有什么优缺点？
#         如果哈希数据来自外部 JSON，键是字符串还是符号？如何转换？

# ==============================================================================
# 第 2 题：面向对象（类 / 模块 / mixin / 访问控制）
# ==============================================================================
# 知识点：
#   1. Ruby 中一切皆对象。类用 class 关键字定义，继承用 < 。
#   2. 构造方法 initialize 在 new 时自动调用。实例变量以 @ 开头。
#   3. attr_accessor / attr_reader / attr_writer 自动生成 getter/setter。
#   4. 模块（Module）无法实例化，主要用途：命名空间 + mixin（混入）。
#      mixin 通过 include（插入实例方法）或 extend（插入类方法）实现"多重继承"效果。
#   5. 访问控制：public（默认）、private（只能隐式 self 调用）、protected（同类实例可调）。
# ==============================================================================

# --- 模块定义：可复用的能力 ---
module Greetable
  def greet
    "你好，我是 #{name}！"   # 依赖混入方提供 name 方法
  end
end

module Countable
  def count_instances
    @instance_count || 0      # 简化的实例计数
  end

  def increment_count
    @instance_count = count_instances + 1
  end
end

# --- 类定义 ---
class Animal
  include Greetable              # 混入实例方法

  attr_accessor :name, :sound    # 自动生成 getter + setter
  attr_reader :age               # 只读

  # 类变量（所有实例共享），以 @@ 开头
  @@total = 0

  def initialize(name, sound, age)
    @name = name
    @sound = sound
    @age = age
    @@total += 1
  end

  # 类方法（属于类本身，不属于实例）
  def self.total_count
    @@total
  end

  def speak
    "#{@name} 发出声音：#{@sound}"
  end

  # 访问控制
  public :speak, :greet

  private

  def secret_method
    "这是私有方法，只能在类内部调用"
  end

  protected

  def compare_age(other)
    # protected 方法允许同类实例之间调用
    @age <=> other.age
  end
end

# --- 子类继承 ---
class Dog < Animal
  def initialize(name, age)
    super(name, "汪汪", age)     # 调用父类构造方法
  end

  def fetch
    "#{@name} 去捡球了！"
  end
end

# --- 使用 ---
dog = Dog.new("旺财", 3)
puts dog.speak                  # 旺财 发出声音：汪汪
puts dog.greet                  # 你好，我是 旺财！
puts dog.fetch                  # 旺财 去捡球了！
puts Animal.total_count         # 1

# --- extend：把模块方法混入为类方法 ---
module Loggable
  def log(msg)
    puts "[LOG] #{msg}"
  end
end

class Cat < Animal
  extend Loggable               # log 成为 Cat 的类方法
  def initialize(name, age)
    super(name, "喵喵", age)
  end
end

cat = Cat.new("咪咪", 2)
Cat.log("创建了一只猫")          # [LOG] 创建了一只猫

# 思考题：include 和 extend 的区别是什么？
#         Ruby 的 mixin 与其他语言的多继承/接口实现有何异同？

# ==============================================================================
# 第 3 题：块 / Proc / Lambda（yield / &block / proc-vs-lambda）
# ==============================================================================
# 知识点：
#   1. 块（Block）不是对象，是代码片段。Proc 是把块"对象化"后的产物。
#   2. yield：在方法内调用传入的块，无需显式声明参数。
#   3. &block：用 & 前缀把块转为 Proc 对象，方便传递和条件调用。
#   4. Proc 与 Lambda 的核心区别：
#      - 参数检查：Lambda 严格检查参数数量，Proc 忽略多余的参数。
#      - return 行为：Lambda 的 return 只返回自身，Proc 的 return 会返回外层方法。
#   5. &（to_proc 约定）：symbol.method 形式的简写依赖 Symbol#to_proc。
# ==============================================================================

# --- yield 基础 ---
def with_timing
  start = Time.now
  yield                         # 执行传入的块
  elapsed = Time.now - start
  puts "耗时 #{elapsed} 秒"
end

with_timing { sleep 0.1 }

# --- &block：把块转为 Proc 对象 ---
def maybe_call(&block)
  if block_given?               # 检查是否传了块
    block.call("被调用了")
  else
    puts "没有块传入"
  end
end

maybe_call { |msg| puts "块说：#{msg}" }
maybe_call                      # 没有块传入

# --- Proc 对象 ---
multiply = Proc.new { |a, b| a * b }
puts multiply.call(3, 4)        # 12
puts multiply.(3, 4)            # 12（简写调用语法）

# --- Lambda 对象 ---
divide = lambda { |a, b| a.to_f / b }
puts divide.call(10, 4)         # 2.5

# Lambda 的 stabby 语法（箭头写法）
square = ->(x) { x * x }
puts square.call(5)             # 25

# --- Proc vs Lambda 的关键区别 ---
# 区别一：参数检查
proc_lenient = Proc.new { |a, b| "a=#{a}, b=#{b}" }
puts proc_lenient.call(1)       # 不报错：a=1, b=   （忽略缺失参数）

lambda_strict = lambda { |a, b| "a=#{a}, b=#{b}" }
begin
  lambda_strict.call(1)         # 报错：wrong number of arguments
rescue ArgumentError => e
  puts "Lambda 参数检查：#{e.message}"
end

# 区别二：return 的行为
def proc_return_test
  p = Proc.new { return 100 }
  p.call                        # Proc 的 return 会直接返回外层方法！
  return 200                    # 这行不会执行
end

def lambda_return_test
  l = lambda { return 100 }
  l.call                        # Lambda 的 return 只返回自身，不影响外层
  return 200                    # 这行会执行
end

puts proc_return_test           # 100
puts lambda_return_test         # 200

# --- &（to_proc）的妙用 ---
# &:upcase 等价于 { |s| s.upcase }
words = %w[hello world ruby]
upcased = words.map(&:upcase)
puts upcased.inspect            # ["HELLO", "WORLD", "RUBY"]

# 思考题：在什么场景下应该用 Lambda 而非 Proc？
#         为什么 map(&:upcase) 能工作？Symbol#to_proc 返回了什么？

# ==============================================================================
# 第 4 题：元编程（method_missing / define_method / open-class）
# ==============================================================================
# 知识点：
#   1. Ruby 允许在运行时动态修改类和对象的行为，这是元编程的核心。
#   2. open-class（打开类）：可以随时重新打开已有类并添加/修改方法。
#   3. define_method：在运行时动态定义方法，常配合代码块使用。
#   4. method_missing：当调用不存在的方法时触发，可实现动态方法分发。
#      注意：使用后应同时覆写 respond_to_missing? 保持一致性。
# ==============================================================================

# --- Open-class：给内置类添加方法 ---
class String
  # 打开 String 类，添加一个自定义方法
  def shout
    upcase + "!!!"
  end
end

puts "hello".shout             # HELLO!!!

# --- define_method：动态定义方法 ---
class Calculator
  # 动态生成 add/subtract/multiply/divide 四个方法
  [:add, :subtract, :multiply, :divide].each_with_index do |name, i|
    define_method(name) do |a, b|
      case name
      when :add then a + b
      when :subtract then a - b
      when :multiply then a * b
      when :divide then a.to_f / b
      end
    end
  end
end

calc = Calculator.new
puts calc.add(1, 2)            # 3
puts calc.multiply(3, 4)       # 12
puts calc.divide(10, 3)        # 3.3333...

# --- method_missing：动态方法分发 ---
class FlexibleHash
  def initialize
    @data = {}
  end

  # 拦截所有未定义的方法调用
  def method_missing(name, *args)
    name_str = name.to_s

    if name_str.end_with?("=")
      # set_xxx= 形式：设置值
      key = name_str.chomp("=").to_sym
      @data[key] = args.first
    elsif name_str.start_with?("get_")
      # get_xxx 形式：读取值
      key = name_str.delete_prefix("get_").to_sym
      @data[key]
    else
      # 以键名作为方法名直接读取
      @data[name]
    end
  end

  # 保持 respond_to? 的一致性
  def respond_to_missing?(name, include_private = false)
    true || super
  end

  def to_s
    @data.inspect
  end
end

fh = FlexibleHash.new
fh.name = "Alice"              # 触发 method_missing → set
fh.age = 25
puts fh.get_name               # Alice
puts fh.get_age                # 25
puts fh                        # {:name=>"Alice", :age=>25}

# 思考题：method_missing 有哪些潜在陷阱？为什么必须实现 respond_to_missing?？
#         过度使用元编程会给代码可读性带来什么问题？

# ==============================================================================
# 第 5 题：DSL 实战（用 Ruby 构建领域特定语言）
# ==============================================================================
# 知识点：
#   1. DSL（Domain-Specific Language）是为特定领域设计的迷你语言。
#   2. Ruby 灵活的语法（可省略括号、块、instance_eval）非常适合构建 DSL。
#   3. instance_eval：在指定对象的上下文中执行块，使块内的方法调用
#      直接作用于该对象——这是构建内部 DSL 的关键技术。
#   4. Builder 模式 + 块 = 声明式配置风格的 DSL。
# ==============================================================================

# --- 目标：构建一个 HTML 生成器 DSL，使用方式如下 ---
#   html = HtmlBuilder.build do
#     div class: "container" do
#       h1 "Hello DSL"
#       p "This is a paragraph"
#       ul do
#         li "Item 1"
#         li "Item 2"
#       end
#     end
#   end
#   puts html
#   => <div class="container"><h1>Hello DSL</h1><p>This is a paragraph</p>...
# ------------------------------------------------------------------------------

class HtmlBuilder
  def initialize
    @children = []
  end

  # 构建入口：类方法 + 块
  def self.build(&block)
    builder = new
    builder.instance_eval(&block)    # 在 builder 上下文中执行块
    builder.to_html
  end

  # method_missing 拦截所有标签方法：div, h1, p, ul, li, span, ...
  def method_missing(tag, *args, &block)
    attrs = args.first.is_a?(Hash) ? args.first : {}
    text  = args.find { |a| a.is_a?(String) }

    inner = if block
              # 有块则递归构建子元素
              child = HtmlBuilder.new
              child.instance_eval(&block)
              child.to_html
            else
              text || ""
            end

    # 生成属性字符串
    attr_str = attrs.map { |k, v| " #{k}=\"#{v}\"" }.join
    @children << "<#{tag}#{attr_str}>#{inner}</#{tag}>"
  end

  def respond_to_missing?(name, include_private = false)
    true || super
  end

  def to_html
    @children.join
  end
end

# --- 使用 DSL ---
html = HtmlBuilder.build do
  div class: "container", id: "main" do
    h1 "Ruby DSL 实战"
    p class: "intro" do
      "用 Ruby 构建领域特定语言"
    end
    ul class: "features" do
      li "简洁的语法"
      li "灵活的元编程"
      li "声明式风格"
    end
  end
end

puts html

# --- 另一个 DSL 示例：配置文件风格 ---
class ServerConfig
  def initialize
    @config = {}
  end

  def self.configure(&block)
    config = new
    config.instance_eval(&block)
    config
  end

  def port(p)
    @config[:port] = p
  end

  def host(h)
    @config[:host] = h
  end

  def environment(env)
    @config[:environment] = env
  end

  def middleware(name, &block)
    @config[:middleware] ||= []
    mw = { name: name }
    if block
      sub = ServerConfig.new
      sub.instance_eval(&block)
      mw[:options] = sub.instance_variable_get(:@config)
    end
    @config[:middleware] << mw
  end

  def to_h
    @config
  end
end

config = ServerConfig.configure do
  host "0.0.0.0"
  port 3000
  environment :production

  middleware :cors do
    environment :strict
  end

  middleware :logger
end

puts config.to_h.inspect

# 思考题：instance_eval 改变了 self 的绑定，这可能带来什么问题？
#         如果 DSL 块内需要访问外部的局部变量，instance_eval 会造成什么影响？
#         如何用 instance_exec 解决这个问题？
