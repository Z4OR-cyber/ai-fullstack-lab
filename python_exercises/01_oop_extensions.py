"""
OOP 扩展练习 —— 的作答
=====================================
完成 01_oop_basics.py 末尾的 5 道扩展练习
"""

from dataclasses import dataclass, field


# =============================================================================
# 扩展 1：给 Book 添加 __eq__ 方法
# =============================================================================
@dataclass
class Book:
    """用 dataclass 重写（同时完成扩展 5），并添加 __eq__"""
    title: str
    author: str
    price: float

    def __str__(self):
        return f"《{self.title}》- {self.author} (¥{self.price})"

    def discount(self, rate):
        return round(self.price * rate, 2)

    def __eq__(self, other):
        """标题和作者相同即判定为相等"""
        if not isinstance(other, Book):
            return NotImplemented
        return self.title == other.title and self.author == other.author

    def __hash__(self):
        """重写 __eq__ 后必须重写 __hash__ 才能作为 dict key / set 元素"""
        return hash((self.title, self.author))


# 测试 __eq__
b1 = Book("Python编程", "Eric Matthes", 89.0)
b2 = Book("Python编程", "Eric Matthes", 59.0)  # 价格不同
b3 = Book("Python编程", "别人写的", 89.0)        # 作者不同
print("=== 扩展1: __eq__ ===")
print(f"b1 == b2 (同书不同价): {b1 == b2}")  # True
print(f"b1 == b3 (同书不同作者): {b1 == b3}")  # False
print(f"b1 in {{b2}}: {b2 in {b1}}")          # True（hash 也一致）


# =============================================================================
# 扩展 2：给 Library 添加 __iter__ 方法
# =============================================================================
class Library:
    def __init__(self, name):
        self.name = name
        self.books = []
        self.users = {}

    def add_book(self, book):
        self.books.append(book)

    def register_user(self, user):
        self.users[user.user_id] = user

    def find_book(self, title):
        for book in self.books:
            if book.title == title:
                return book
        return None

    def remove_book(self, title):
        """删除图书（供 Admin 调用）"""
        for i, book in enumerate(self.books):
            if book.title == title:
                return self.books.pop(i)
        return None

    def __len__(self):
        return len(self.books)

    def __contains__(self, title):
        return any(book.title == title for book in self.books)

    def __iter__(self):
        """支持 for book in library 遍历"""
        return iter(self.books)

    def __str__(self):
        return f"📚 {self.name} (藏书{len(self.books)}本, 注册用户{len(self.users)}人)"


# 测试 __iter__
lib = Library("测试图书馆")
lib.add_book(Book("A", "Author A", 10.0))
lib.add_book(Book("B", "Author B", 20.0))
lib.add_book(Book("C", "Author C", 30.0))
print("\n=== 扩展2: __iter__ ===")
for book in lib:
    print(f"  {book}")


# =============================================================================
# 扩展 3：给 User 添加借阅历史记录
# =============================================================================
class User:
    max_borrow = 3

    def __init__(self, name, user_id):
        self.name = name
        self.user_id = user_id
        self.borrowed = []
        self.history = []  # 借阅历史：每条 (动作, 书名, 时间戳)

    def borrow(self, book):
        if len(self.borrowed) >= self.max_borrow:
            self.history.append(("borrow_failed", book.title, "上限"))
            return f"❌ {self.name}已达借阅上限({self.max_borrow}本)"
        self.borrowed.append(book)
        self.history.append(("borrow", book.title, "ok"))
        return f"✅ {self.name}借阅了《{book.title}》"

    def return_book(self, book_title):
        for i, book in enumerate(self.borrowed):
            if book.title == book_title:
                self.borrowed.pop(i)
                self.history.append(("return", book_title, "ok"))
                return f"✅ {self.name}归还了《{book_title}》"
        self.history.append(("return_failed", book_title, "未借阅"))
        return f"❌ {self.name}没有借阅《{book_title}》"

    def show_history(self):
        """打印借阅历史"""
        print(f"📋 {self.name} 的借阅历史:")
        for action, title, status in self.history:
            print(f"  [{action}] 《{title}》({status})")

    def __str__(self):
        return f"[{self.__class__.__name__}] {self.name} (ID:{self.user_id}, 已借{len(self.borrowed)}/{self.max_borrow})"


# 测试借阅历史
print("\n=== 扩展3: 借阅历史 ===")
u = User("Charlie", "U100")
u.borrow(Book("Python编程", "Eric Matthes", 89.0))
u.borrow(Book("流畅的Python", "Luciano Ramalho", 139.0))
u.borrow(Book("算法导论", "Cormen", 128.0))
u.borrow(Book("机器学习", "周志华", 88.0))  # 失败
u.return_book("Python编程")
u.return_book("不存在的书")  # 失败
u.show_history()


# =============================================================================
# 扩展 4：LibraryAdmin 类继承 User，拥有添加/删除图书权限
# =============================================================================
class LibraryAdmin(User):
    """管理员：可以添加和删除图书，借阅上限无限"""
    max_borrow = 999

    def __init__(self, name, user_id, library=None):
        super().__init__(name, user_id)
        self.library = library  # 管理的图书馆

    def add_book(self, book):
        if self.library:
            self.library.add_book(book)
            return f"🔧 管理员 {self.name} 添加了《{book.title}》"
        return "❌ 未关联图书馆"

    def remove_book(self, title):
        if self.library:
            removed = self.library.remove_book(title)
            if removed:
                return f"🔧 管理员 {self.name} 删除了《{removed.title}》"
            return f"❌ 图书馆没有《{title}》"
        return "❌ 未关联图书馆"

    def __str__(self):
        return f"[Admin] {self.name} (ID:{self.user_id}, 管理:{self.library.name if self.library else '无'})"


# 测试 LibraryAdmin
print("\n=== 扩展4: LibraryAdmin ===")
admin_lib = Library("管理员测试馆")
admin_lib.add_book(Book("旧书", "旧作者", 5.0))

admin = LibraryAdmin("AdminZ", "A001", admin_lib)
print(admin)
print(admin.add_book(Book("新书", "新作者", 50.0)))
print(f"当前藏书: {len(admin_lib)}本")
print(admin.remove_book("旧书"))
print(f"删除后藏书: {len(admin_lib)}本")
# 管理员也能借书
print(admin.borrow(Book("临时借阅", "某作者", 10.0)))


# =============================================================================
# 扩展 5：用 dataclass 重写 Book 类（已在扩展1完成）
# =============================================================================
print("\n=== 扩展5: dataclass ===")
dc_book = Book("Dataclass入门", "Python", 0.0)
print(f"dataclass 自动生成 __init__: {dc_book}")
print(f"dataclass 自动生成 __repr__: {repr(dc_book)}")
# dataclass 自动生成了 __eq__，但我们重写了它只比较 title+author
dc_book2 = Book("Dataclass入门", "Python", 99.0)
print(f"不同价格的同一本书相等: {dc_book == dc_book2}")

# dataclass 的 fields
import dataclasses
print(f"字段列表: {[f.name for f in dataclasses.fields(dc_book)]}")


# =============================================================================
# 学习总结
# =============================================================================
print("\n" + "=" * 60)
print("✅ OOP 基础全部掌握，核心知识点：")
print("=" * 60)
summary = """
1. 类与对象：__init__ 构造、self 实例引用、实例属性 vs 类属性
2. 继承与多态：子类继承父类、super() 调用、NotImplementedError 抽象方法、鸭子类型
3. 魔法方法：__str__/__repr__/__len__/__eq__/__add__/__getitem__/__iter__/__contains__
4. 装饰器：@property（getter+setter）、@classmethod（cls 工厂方法）、@staticmethod
5. dataclass：自动生成 __init__/__repr__/__eq__，减少样板代码
6. 关键细节：重写 __eq__ 后必须重写 __hash__；@property setter 可做校验
"""
print(summary)
