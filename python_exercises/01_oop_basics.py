"""
Python 面向对象编程基础练习
=====================================
对应学习路线图：第一阶段 - 筑基期 - 面向对象编程
目标：掌握类、继承、多态、魔法方法，最终用 OOP 重构一个小项目

运行方式：python 01_oop_basics.py
"""

# =============================================================================
# 知识点讲解
# =============================================================================
#
# 1. 类与对象
#    - 类是蓝图/模板，对象是根据蓝图创建的实例
#    - __init__ 是构造方法，创建对象时自动调用
#    - self 代表当前实例本身
#
# 2. 继承
#    - 子类继承父类的属性和方法，实现代码复用
#    - Python 支持多继承（通过 MRO 解决冲突）
#    - super() 调用父类方法
#
# 3. 多态
#    - 不同类的对象调用同名方法，表现出不同行为
#    - Python 的多态是"鸭子类型"——不关心类型，只关心行为
#
# 4. 魔法方法（Dunder Methods）
#    - __init__   : 构造方法
#    - __str__    : 用户友好的字符串表示（print 时调用）
#    - __repr__   : 开发者友好的字符串表示（调试时调用）
#    - __eq__     : 定义 == 行为
#    - __len__    : 定义 len() 行为
#    - __getitem__: 定义 [] 访问行为
#    - __iter__   : 定义迭代行为
#
# 5. 类方法 vs 静态方法 vs 实例方法
#    - 实例方法: def method(self)，访问实例属性
#    - 类方法:   @classmethod def method(cls)，访问类属性
#    - 静态方法: @staticmethod def method()，不访问实例或类属性


# =============================================================================
# 练习 1（入门）：创建一个简单的 Book 类
# =============================================================================
"""
要求：
  1. 创建 Book 类，包含 title、author、price 属性
  2. 实现 __str__ 方法，打印时显示 "《title》- author (¥price)"
  3. 实现 discount 方法，传入折扣率返回折后价格

提示：
  - 使用 __init__ 初始化属性
  - __str__ 返回字符串
"""

# ------ 参考答案 ------
class Book:
    def __init__(self, title, author, price):
        self.title = title
        self.author = author
        self.price = price

    def __str__(self):
        return f"《{self.title}》- {self.author} (¥{self.price})"

    def discount(self, rate):
        """rate: 折扣率，如 0.8 表示 8 折"""
        return round(self.price * rate, 2)


# 测试
book = Book("Python编程", "Eric Matthes", 89.0)
print(book)                    # 《Python编程》- Eric Matthes (¥89.0)
print(f"8折后价格: ¥{book.discount(0.8)}")  # 8折后价格: ¥71.2


# =============================================================================
# 练习 2（进阶）：继承与多态 —— 动物王国
# =============================================================================
"""
要求：
  1. 创建 Animal 基类，包含 name 属性和 speak 方法（基类抛出 NotImplementedError）
  2. 创建 Dog、Cat、Duck 子类，各自实现 speak 方法
  3. 编写 make_sound 函数，接收 Animal 列表，让每个动物发声
  4. Dog 额外增加 fetch 方法（捡球），其他动物没有

提示：
  - 基类 speak 抛异常强制子类实现 → 这就是"抽象方法"的简单写法
  - make_sound 不关心具体类型，只调用 speak → 这就是多态
"""

# ------ 参考答案 ------
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        raise NotImplementedError("子类必须实现 speak 方法")

    def __str__(self):
        return f"{self.__class__.__name__}({self.name})"


class Dog(Animal):
    def speak(self):
        return f"{self.name}: 汪汪汪！"

    def fetch(self):
        return f"{self.name} 捡回了球！"


class Cat(Animal):
    def speak(self):
        return f"{self.name}: 喵~"


class Duck(Animal):
    def speak(self):
        return f"{self.name}: 嘎嘎嘎！"


def make_sound(animals):
    """多态：不关心具体类型，统一调用 speak"""
    for animal in animals:
        print(animal.speak())


# 测试
animals = [Dog("旺财"), Cat("咪咪"), Duck("唐老鸭")]
make_sound(animals)
# 旺财: 汪汪汪！
# 咪咪: 喵~
# 唐老鸭: 嘎嘎嘎！

dog = Dog("旺财")
print(dog.fetch())  # 只有 Dog 有 fetch 方法


# =============================================================================
# 练习 3（中阶）：魔法方法 —— 自定义可迭代的购物车
# =============================================================================
"""
要求：
  1. 创建 ShoppingCart 类，内部用列表存储商品
  2. 实现以下魔法方法：
     - __len__     : 返回商品数量
     - __str__     : 显示购物车摘要
     - __add__     : 支持购物车相加（合并商品）
     - __getitem__ : 支持下标访问 cart[0]
     - __iter__    : 支持 for item in cart 遍历
  3. 实现 total_price 方法返回总价
"""

# ------ 参考答案 ------
class ShoppingCart:
    def __init__(self, items=None):
        # items 是 Book 对象的列表
        self.items = items if items is not None else []

    def add(self, book):
        self.items.append(book)
        return self  # 链式调用

    def total_price(self):
        return sum(book.price for book in self.items)

    def __len__(self):
        return len(self.items)

    def __str__(self):
        return f"购物车({len(self.items)}件商品, 总价¥{self.total_price()})"

    def __add__(self, other):
        """合并两个购物车"""
        return ShoppingCart(self.items + other.items)

    def __getitem__(self, index):
        return self.items[index]

    def __iter__(self):
        return iter(self.items)


# 测试
cart1 = ShoppingCart()
cart1.add(Book("Python编程", "Eric Matthes", 89.0))
cart1.add(Book("流畅的Python", "Luciano Ramalho", 139.0))

cart2 = ShoppingCart()
cart2.add(Book("算法导论", "Cormen", 128.0))

print(cart1)  # 购物车(2件商品, 总价¥228.0)
print(len(cart1))  # 2

# 合并购物车
cart3 = cart1 + cart2
print(cart3)  # 购物车(3件商品, 总价¥356.0)

# 遍历
for item in cart3:
    print(f"  - {item}")

# 下标访问
print(f"第一本书: {cart3[0]}")


# =============================================================================
# 练习 4（高阶）：类方法、静态方法与属性装饰器
# =============================================================================
"""
要求：
  1. 创建 Temperature 类，可以用 Celsius 或 Fahrenheit 创建
  2. 用 @property 让 celsius 和 fahrenheit 互相转换
  3. 用 @classmethod 提供 from_fahrenheit 工厂方法
  4. 用 @staticmethod 提供水冰点/沸点常量查询

提示：
  - @property 把方法变成属性访问：obj.celsius 而不是 obj.celsius()
  - @classmethod 的第一个参数是类本身(cls)，常用于工厂方法
  - @staticmethod 不接收 self 或 cls，就是放在类命名空间下的普通函数
"""

# ------ 参考答案 ------
class Temperature:
    def __init__(self, celsius):
        self._celsius = celsius

    @property
    def celsius(self):
        return self._celsius

    @celsius.setter
    def celsius(self, value):
        if value < -273.15:
            raise ValueError("温度不能低于绝对零度 (-273.15°C)")
        self._celsius = value

    @property
    def fahrenheit(self):
        return self._celsius * 9 / 5 + 32

    @classmethod
    def from_fahrenheit(cls, f):
        """工厂方法：用华氏度创建 Temperature 对象"""
        return cls((f - 32) * 5 / 9)

    @staticmethod
    def water_freezing_point():
        """水冰点（常量查询）"""
        return 0.0

    @staticmethod
    def water_boiling_point():
        """水沸点（常量查询）"""
        return 100.0

    def __str__(self):
        return f"{self._celsius:.1f}°C / {self.fahrenheit:.1f}°F"


# 测试
t1 = Temperature(25)
print(t1)  # 25.0°C / 77.0°F

t2 = Temperature.from_fahrenheit(100)
print(t2)  # 37.8°C / 100.0°F

print(f"水冰点: {Temperature.water_freezing_point()}°C")
print(f"水沸点: {Temperature.water_boiling_point()}°C")


# =============================================================================
# 实战小项目：简易图书管理系统（OOP 综合）
# =============================================================================
"""
项目说明：
  用 OOP 构建一个命令行图书管理系统，综合运用：
  - 类与对象（Book、User、Library）
  - 继承（不同类型的用户：普通用户、VIP用户）
  - 多态（不同用户的借阅上限不同）
  - 魔法方法（__str__、__len__、__contains__）
  - 类方法（从配置创建）

运行后会输出模拟操作结果。
"""

class User:
    """用户基类"""
    max_borrow = 3  # 类属性：最大借阅数

    def __init__(self, name, user_id):
        self.name = name
        self.user_id = user_id
        self.borrowed = []

    def borrow(self, book):
        if len(self.borrowed) >= self.max_borrow:
            return f"❌ {self.name}已达借阅上限({self.max_borrow}本)"
        self.borrowed.append(book)
        return f"✅ {self.name}借阅了《{book.title}》"

    def return_book(self, book_title):
        for i, book in enumerate(self.borrowed):
            if book.title == book_title:
                self.borrowed.pop(i)
                return f"✅ {self.name}归还了《{book_title}》"
        return f"❌ {self.name}没有借阅《{book_title}》"

    def __str__(self):
        return f"[{self.__class__.__name__}] {self.name} (ID:{self.user_id}, 已借{len(self.borrowed)}/{self.max_borrow})"


class VIPUser(User):
    """VIP用户：借阅上限更高"""
    max_borrow = 10

    def borrow(self, book):
        # VIP 可以借阅所有书，没有限制（演示多态）
        self.borrowed.append(book)
        return f"✅ VIP {self.name}借阅了《{book.title}》(VIP无上限特权)"


class Library:
    """图书馆：管理图书和用户"""

    def __init__(self, name):
        self.name = name
        self.books = []      # 所有图书
        self.users = {}      # user_id -> User

    def add_book(self, book):
        self.books.append(book)

    def register_user(self, user):
        self.users[user.user_id] = user

    def find_book(self, title):
        """查找图书"""
        for book in self.books:
            if book.title == title:
                return book
        return None

    def __len__(self):
        return len(self.books)

    def __contains__(self, title):
        """支持 'title' in library 语法"""
        return any(book.title == title for book in self.books)

    def __str__(self):
        return f"📚 {self.name} (藏书{len(self.books)}本, 注册用户{len(self.users)}人)"


# ---- 运行实战项目 ----
print("\n" + "=" * 60)
print("📚 简易图书管理系统演示")
print("=" * 60)

# 创建图书馆
lib = Library("城市中央图书馆")

# 添加图书
lib.add_book(Book("Python编程", "Eric Matthes", 89.0))
lib.add_book(Book("流畅的Python", "Luciano Ramalho", 139.0))
lib.add_book(Book("算法导论", "Cormen", 128.0))
lib.add_book(Book("深度学习", "Goodfellow", 199.0))
lib.add_book(Book("机器学习", "周志华", 88.0))

print(lib)
print(f"是否有《深度学习》: {'深度学习' in lib}")

# 注册用户
alice = User("Alice", "U001")
bob = VIPUser("Bob", "V001")
lib.register_user(alice)
lib.register_user(bob)

print(alice)
print(bob)

# 借阅操作
print("\n--- 借阅操作 ---")
print(alice.borrow(lib.find_book("Python编程")))
print(alice.borrow(lib.find_book("流畅的Python")))
print(alice.borrow(lib.find_book("算法导论")))
print(alice.borrow(lib.find_book("机器学习")))  # 达到上限

print(bob.borrow(lib.find_book("深度学习")))

# 归还操作
print("\n--- 归还操作 ---")
print(alice.return_book("算法导论"))
print(alice.borrow(lib.find_book("机器学习")))  # 归还后可以再借

# 最终状态
print("\n--- 最终状态 ---")
print(alice)
print(bob)


# =============================================================================
# 扩展练习（选做）
# =============================================================================
"""
1. 给 Book 添加 __eq__ 方法，使两本书标题和作者相同时判定为相等
2. 给 Library 添加 __iter__ 方法，支持 for book in library 遍历
3. 给 User 添加借阅历史记录功能，用列表存储每次借还记录
4. 实现一个 LibraryAdmin 类继承 User，拥有添加/删除图书的权限
5. 用 dataclass 装饰器重写 Book 类（from dataclasses import dataclass）
"""
