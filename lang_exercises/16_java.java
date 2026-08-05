// ============================================================
// 阶段九：Java 进阶编程练习
// 题数：10题
// 创建日期：2026-08-05
// 说明：从零开始掌握Java核心特性，涵盖OOP到设计模式
// 运行方式：javac JavaExercises.java && java JavaExercises
// ============================================================

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.stream.*;
import java.util.function.*;
import java.lang.reflect.*;
import java.lang.annotation.*;

class JavaExercises {

    // ============================================================
    // 嵌套类定义（各练习所需）
    // ============================================================

    // ---- 第1题：OOP核心 ----

    // 抽象类：不能实例化，可包含抽象方法和具体方法
    static abstract class Animal {
        protected String name;
        protected int age;

        Animal(String name, int age) {
            this.name = name;
            this.age = age;
        }

        // 抽象方法：子类必须实现
        abstract void speak();

        // 具体方法：子类可直接继承使用
        void info() {
            System.out.println("  " + name + ", " + age + "岁");
        }

        // final方法：子类不能重写
        final void breathe() {
            System.out.println("  " + name + " 在呼吸");
        }
    }

    // 接口：定义行为契约，支持多实现
    interface Swimmer {
        void swim();  // 默认 public abstract
    }

    // 子类：继承抽象类，必须实现所有抽象方法
    static class Dog extends Animal {
        Dog(String name, int age) { super(name, age); }

        @Override
        void speak() { System.out.println("  " + name + ": 汪汪！"); }
    }

    static class Cat extends Animal {
        Cat(String name, int age) { super(name, age); }

        @Override
        void speak() { System.out.println("  " + name + ": 喵喵！"); }
    }

    // 多实现：继承类 + 实现接口
    static class Fish extends Animal implements Swimmer {
        Fish(String name, int age) { super(name, age); }

        @Override
        void speak() { System.out.println("  " + name + ": ...（吐泡泡）"); }

        @Override
        public void swim() { System.out.println("  " + name + " 在水中游泳"); }
    }

    // ---- 第2题：泛型 ----
    static class Box<T> {
        private T value;

        Box(T value) { this.value = value; }
        T get() { return value; }
        void set(T value) { this.value = value; }
    }

    // ---- 第4题：Stream API ----
    static class Person {
        String name;
        int age;
        String city;

        Person(String name, int age, String city) {
            this.name = name;
            this.age = age;
            this.city = city;
        }

        String getName() { return name; }
        int getAge() { return age; }
        String getCity() { return city; }

        public String toString() {
            return name + "(" + age + "," + city + ")";
        }
    }

    // ---- 第6题：异常处理 ----

    // Checked异常：继承Exception，必须try-catch或声明throws
    static class InsufficientFundsException extends Exception {
        InsufficientFundsException(String msg) { super(msg); }
    }

    // 实现AutoCloseable的资源类（用于try-with-resources）
    static class ResourceFile implements AutoCloseable {
        private String name;

        ResourceFile(String name) {
            this.name = name;
            System.out.println("  [ResourceFile] 打开: " + name);
        }

        public void close() {
            System.out.println("  [ResourceFile] 自动关闭: " + name);
        }
    }

    // ---- 第8题：注解与反射 ----

    // 自定义注解：运行时保留，作用于方法
    @Retention(RetentionPolicy.RUNTIME)
    @Target(ElementType.METHOD)
    @interface MyLog {
        String value() default "";
    }

    // 目标接口
    interface GreetingService {
        void sayHello(String name);
    }

    // 目标实现
    static class GreetingImpl implements GreetingService {
        @MyLog("打招呼方法")
        public void sayHello(String name) {
            System.out.println("  Hello, " + name + "!");
        }
    }

    // 动态代理处理器
    static class LogHandler implements InvocationHandler {
        private Object target;

        LogHandler(Object target) { this.target = target; }

        public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
            System.out.println("  [代理] 调用前: " + method.getName());
            Object result = method.invoke(target, args);
            System.out.println("  [代理] 调用后: " + method.getName());
            return result;
        }
    }

    // ---- 第10题：设计模式 ----

    // 1. 单例模式（枚举实现，线程安全）
    enum Singleton {
        INSTANCE;
        private int value = 0;
        public int getValue() { return value; }
        public void setValue(int v) { value = v; }
    }

    // 2. 工厂模式
    interface Pet {
        void speak();
    }

    static class DogPet implements Pet {
        public void speak() { System.out.println("  汪汪！"); }
    }

    static class CatPet implements Pet {
        public void speak() { System.out.println("  喵喵！"); }
    }

    static class PetFactory {
        static Pet create(String type) {
            if ("dog".equals(type)) return new DogPet();
            if ("cat".equals(type)) return new CatPet();
            throw new IllegalArgumentException("未知宠物: " + type);
        }
    }

    // 3. 策略模式
    interface SortStrategy {
        void sort(int[] arr);
        String getName();
    }

    static class BubbleSort implements SortStrategy {
        public void sort(int[] arr) {
            for (int i = 0; i < arr.length - 1; i++)
                for (int j = 0; j < arr.length - 1 - i; j++)
                    if (arr[j] > arr[j + 1]) {
                        int t = arr[j]; arr[j] = arr[j + 1]; arr[j + 1] = t;
                    }
        }
        public String getName() { return "冒泡排序"; }
    }

    static class QuickSort implements SortStrategy {
        public void sort(int[] arr) {
            quickSort(arr, 0, arr.length - 1);
        }
        private void quickSort(int[] arr, int lo, int hi) {
            if (lo >= hi) return;
            int pivot = arr[hi];
            int i = lo - 1;
            for (int j = lo; j < hi; j++) {
                if (arr[j] < pivot) {
                    i++;
                    int t = arr[i]; arr[i] = arr[j]; arr[j] = t;
                }
            }
            int t = arr[i + 1]; arr[i + 1] = arr[hi]; arr[hi] = t;
            quickSort(arr, lo, i);
            quickSort(arr, i + 2, hi);
        }
        public String getName() { return "快速排序"; }
    }

    static class ArraySorter {
        private SortStrategy strategy;
        void setStrategy(SortStrategy s) { strategy = s; }
        void sort(int[] arr) {
            System.out.println("  使用" + strategy.getName() + ":");
            strategy.sort(arr);
            System.out.print("  结果: ");
            for (int v : arr) System.out.print(v + " ");
            System.out.println();
        }
    }

    // 4. 观察者模式
    interface MyObserver {
        void update(String news);
    }

    static class NewsSubject {
        private List<MyObserver> observers = new ArrayList<>();

        void subscribe(MyObserver o) { observers.add(o); }
        void unsubscribe(MyObserver o) { observers.remove(o); }

        void publish(String news) {
            System.out.println("  [发布新闻] " + news);
            for (MyObserver o : observers) o.update(news);
        }
    }

    static class NewsReader implements MyObserver {
        private String name;

        NewsReader(String name) { this.name = name; }

        public void update(String news) {
            System.out.println("  " + name + " 收到: " + news);
        }
    }

    // 5. 装饰器模式
    interface Coffee {
        String getDescription();
        double cost();
    }

    static class BasicCoffee implements Coffee {
        public String getDescription() { return "基础咖啡"; }
        public double cost() { return 15.0; }
    }

    abstract static class CoffeeDecorator implements Coffee {
        protected Coffee coffee;
        CoffeeDecorator(Coffee c) { coffee = c; }
    }

    static class MilkDecorator extends CoffeeDecorator {
        MilkDecorator(Coffee c) { super(c); }
        public String getDescription() { return coffee.getDescription() + " + 牛奶"; }
        public double cost() { return coffee.cost() + 5.0; }
    }

    static class SugarDecorator extends CoffeeDecorator {
        SugarDecorator(Coffee c) { super(c); }
        public String getDescription() { return coffee.getDescription() + " + 糖"; }
        public double cost() { return coffee.cost() + 2.0; }
    }

    // ============================================================
    // 静态辅助方法
    // ============================================================

    // 泛型方法：找最大值（类型参数需实现Comparable）
    static <T extends Comparable<T>> T findMax(T[] arr) {
        T max = arr[0];
        for (T item : arr) {
            if (item.compareTo(max) > 0) max = item;
        }
        return max;
    }

    // 上界通配符：接受Number及其子类的List
    static double sumOfList(List<? extends Number> list) {
        double sum = 0;
        for (Number n : list) sum += n.doubleValue();
        return sum;
    }

    // 模拟取款（抛出Checked异常）
    static void withdraw(double balance, double amount) throws InsufficientFundsException {
        if (amount > balance) {
            throw new InsufficientFundsException(
                "余额不足: 余额=" + balance + ", 取款=" + amount);
        }
        System.out.println("  取款成功: " + amount);
    }

    // ============================================================
    // 练习方法
    // ============================================================

    // ===== 第1题：OOP核心 =====
    // 知识点：
    // Java是纯面向对象语言，一切皆对象。类是对象的模板，包含字段和方法。
    // 继承（extends）实现代码复用，多态通过动态绑定实现（父类引用指向子类对象）。
    // 抽象类（abstract）定义模板，接口（interface）定义契约。
    // Java单继承（类）但可多实现（接口），通过接口弥补单继承限制。
    static void exercise1() {
        System.out.println("===== 第1题：OOP核心 =====");

        // 多态：父类引用指向子类对象
        System.out.println("--- 1. 多态 ---");
        Animal[] animals = {
            new Dog("旺财", 3),
            new Cat("咪咪", 2),
            new Fish("Nemo", 1)
        };

        for (Animal a : animals) {
            a.speak();  // 动态绑定：调用实际类型的方法
            a.info();   // 继承的公共方法
        }

        // 接口的使用
        System.out.println("--- 2. 接口 ---");
        Swimmer swimmer = new Fish("金鱼", 1);
        swimmer.swim();

        // 向上转型与向下转型
        System.out.println("--- 3. 类型转换 ---");
        Animal animal = new Dog("大黄", 5);  // 向上转型（自动）
        animal.speak();
        if (animal instanceof Dog) {
            Dog dog = (Dog) animal;  // 向下转型（需强制）
            System.out.println("  向下转型成功: " + dog.name);
        }

        // final关键字
        System.out.println("--- 4. final ---");
        Dog d = new Dog("小白", 4);
        d.breathe();  // final方法不可重写但可调用
        final int MAX = 100;  // final变量不可修改
        System.out.println("  final变量 MAX = " + MAX);

        // 思考题：接口和抽象类有什么区别？什么时候用接口，什么时候用抽象类？
        // 提示：接口定义"能做什么"（行为契约），抽象类定义"是什么"（模板复用）。
        System.out.println();
    }

    // ===== 第2题：泛型 =====
    // 知识点：
    // 泛型允许类型参数化，编译期类型安全，消除强制转换。
    // Java泛型通过"类型擦除"实现：编译后泛型类型信息被擦除，运行时不存在。
    // 通配符：? extends T（上界，只读）、? super T（下界，只写）。
    // PECS原则：Producer Extends, Consumer Super。
    static void exercise2() {
        System.out.println("===== 第2题：泛型 =====");

        // 1. 泛型类
        System.out.println("--- 1. 泛型类 ---");
        Box<String> strBox = new Box<>("Hello Generics");
        Box<Integer> intBox = new Box<>(42);
        System.out.println("  字符串盒子: " + strBox.get());
        System.out.println("  整数盒子: " + intBox.get());

        // 2. 泛型方法
        System.out.println("--- 2. 泛型方法 ---");
        Integer[] nums = {3, 1, 4, 1, 5, 9, 2, 6};
        String[] words = {"banana", "apple", "cherry"};
        System.out.println("  最大整数: " + findMax(nums));
        System.out.println("  最大字符串: " + findMax(words));

        // 3. 通配符
        System.out.println("--- 3. 通配符 ---");
        List<Integer> intList = Arrays.asList(1, 2, 3);
        List<Double> dblList = Arrays.asList(1.5, 2.5, 3.5);
        System.out.println("  整数列表和: " + sumOfList(intList));   // ? extends Number
        System.out.println("  浮点列表和: " + sumOfList(dblList));

        // 4. 类型擦除演示
        System.out.println("--- 4. 类型擦除 ---");
        Box<String> b1 = new Box<>("A");
        Box<Integer> b2 = new Box<>(1);
        System.out.println("  b1.getClass() == b2.getClass(): "
            + (b1.getClass() == b2.getClass()));
        System.out.println("  (运行时泛型类型信息被擦除，两者都是Box类)");

        // 5. 泛型限制
        System.out.println("--- 5. 泛型限制 ---");
        System.out.println("  不能new T()：类型擦除后T变为Object，无法确定实际类型");
        System.out.println("  不能new T[]：数组协变与泛型不兼容");
        System.out.println("  不能使用基本类型：List<int>不合法，需用List<Integer>");

        // 思考题：为什么List<Integer>不能赋值给List<Number>？
        // 提示：泛型不协变。若允许，可通过List<Number>添加Double，破坏类型安全。
        System.out.println();
    }

    // ===== 第3题：集合框架 =====
    // 知识点：
    // Java集合框架分为两大体系：Collection（单列）和Map（双列）。
    // List：有序可重复（ArrayList数组实现、LinkedList链表实现）。
    // Set：无序不可重复（HashSet哈希表、TreeSet红黑树）。
    // Map：键值对（HashMap哈希表、TreeMap红黑树、LinkedHashMap保持插入序）。
    // Queue：队列（LinkedList、PriorityQueue优先队列）。
    static void exercise3() {
        System.out.println("===== 第3题：集合框架 =====");

        // 1. List（有序，可重复）
        System.out.println("--- 1. List（ArrayList）---");
        List<String> list = new ArrayList<>();
        list.add("Java");
        list.add("Python");
        list.add("C++");
        list.add(1, "Go");  // 在索引1处插入
        System.out.println("  列表: " + list);
        System.out.println("  索引2: " + list.get(2));
        list.remove("Go");
        System.out.println("  移除Go后: " + list);
        System.out.println("  大小: " + list.size());

        // 2. Set（不可重复）
        System.out.println("--- 2. Set ---");
        Set<String> set = new HashSet<>();
        set.add("苹果");
        set.add("香蕉");
        set.add("苹果");  // 重复不会添加
        set.add("橙子");
        System.out.println("  HashSet: " + set);
        System.out.println("  包含香蕉: " + set.contains("香蕉"));
        System.out.println("  大小: " + set.size() + " (自动去重)");

        Set<Integer> treeSet = new TreeSet<>();
        treeSet.add(30); treeSet.add(10); treeSet.add(20);
        System.out.println("  TreeSet(有序): " + treeSet);

        // 3. Map（键值对）
        System.out.println("--- 3. Map（HashMap）---");
        Map<String, Integer> map = new HashMap<>();
        map.put("Alice", 95);
        map.put("Bob", 87);
        map.put("Charlie", 92);
        System.out.println("  Alice的分数: " + map.get("Alice"));
        System.out.println("  包含Bob: " + map.containsKey("Bob"));
        System.out.println("  遍历:");
        map.forEach((k, v) -> System.out.println("    " + k + " = " + v));

        // 4. Queue
        System.out.println("--- 4. Queue ---");
        Queue<String> queue = new LinkedList<>();
        queue.offer("任务1");
        queue.offer("任务2");
        queue.offer("任务3");
        System.out.println("  队列: " + queue);
        System.out.println("  取出: " + queue.poll());
        System.out.println("  剩余: " + queue);

        // PriorityQueue（优先队列，最小堆）
        PriorityQueue<Integer> pq = new PriorityQueue<>();
        pq.offer(5); pq.offer(1); pq.offer(3); pq.offer(4); pq.offer(2);
        System.out.print("  优先队列出队顺序: ");
        while (!pq.isEmpty()) System.out.print(pq.poll() + " ");
        System.out.println();

        // 5. 集合工具
        System.out.println("--- 5. Collections工具 ---");
        List<Integer> nums = new ArrayList<>(Arrays.asList(5, 2, 8, 1, 9));
        Collections.sort(nums);
        System.out.println("  排序: " + nums);
        Collections.reverse(nums);
        System.out.println("  反转: " + nums);
        System.out.println("  最大: " + Collections.max(nums));
        System.out.println("  二分查找8: 索引=" + Collections.binarySearch(nums, 8));

        // 思考题：HashMap和TreeMap在性能上有什么区别？分别适合什么场景？
        // 提示：HashMap O(1)查找但不保证顺序，TreeMap O(logn)但保持键有序。
        System.out.println();
    }

    // ===== 第4题：Stream API =====
    // 知识点：
    // Stream API是Java 8引入的函数式数据处理工具，支持声明式操作集合。
    // 核心操作：filter（过滤）、map（映射）、reduce（归约）、collect（收集）。
    // Stream分为中间操作（惰性求值）和终端操作（触发计算）。
    // 常用收集器：toList、groupingBy、joining、counting等。
    static void exercise4() {
        System.out.println("===== 第4题：Stream API =====");

        List<Person> people = Arrays.asList(
            new Person("Alice", 25, "北京"),
            new Person("Bob", 30, "上海"),
            new Person("Charlie", 35, "北京"),
            new Person("David", 28, "深圳"),
            new Person("Eve", 32, "上海"),
            new Person("Frank", 22, "北京")
        );

        // 1. filter（过滤）
        System.out.println("--- 1. filter（过滤）---");
        people.stream()
            .filter(p -> p.getAge() > 28)
            .forEach(p -> System.out.println("  " + p));

        // 2. map（映射）
        System.out.println("--- 2. map（映射）---");
        List<String> names = people.stream()
            .map(Person::getName)
            .collect(Collectors.toList());
        System.out.println("  所有名字: " + names);

        // 3. reduce（归约）
        System.out.println("--- 3. reduce（归约）---");
        int totalAge = people.stream()
            .map(Person::getAge)
            .reduce(0, Integer::sum);
        System.out.println("  年龄总和: " + totalAge);

        Optional<Integer> maxAge = people.stream()
            .map(Person::getAge)
            .reduce(Integer::max);
        System.out.println("  最大年龄: " + maxAge.orElse(-1));

        // 4. collect（分组分区）
        System.out.println("--- 4. collect（分组）---");
        Map<String, List<Person>> byCity = people.stream()
            .collect(Collectors.groupingBy(Person::getCity));
        byCity.forEach((city, list) ->
            System.out.println("  " + city + ": " + list.size() + "人"));

        // 分区（按条件分为两组）
        Map<Boolean, List<Person>> partition = people.stream()
            .collect(Collectors.partitioningBy(p -> p.getAge() >= 30));
        System.out.println("  >=30岁: " + partition.get(true).size() + "人");
        System.out.println("  <30岁: " + partition.get(false).size() + "人");

        // 5. 综合链式操作
        System.out.println("--- 5. 综合操作 ---");
        double avgAgeInBJ = people.stream()
            .filter(p -> p.getCity().equals("北京"))
            .mapToInt(Person::getAge)
            .average()
            .orElse(0);
        System.out.println("  北京平均年龄: " + avgAgeInBJ);

        String oldestName = people.stream()
            .max(Comparator.comparingInt(Person::getAge))
            .map(Person::getName)
            .orElse("无");
        System.out.println("  最年长: " + oldestName);

        // 字符串拼接
        String allNames = people.stream()
            .map(Person::getName)
            .collect(Collectors.joining(", ", "[", "]"));
        System.out.println("  名字拼接: " + allNames);

        // 思考题：stream()和parallelStream()有什么区别？什么场景适合并行流？
        // 提示：parallelStream利用ForkJoinPool并行处理，适合大数据量无状态操作。
        System.out.println();
    }

    // ===== 第5题：并发编程 =====
    // 知识点：
    // Java并发核心：Thread/Runnable创建线程，Lock接口替代synchronized提供更灵活锁控制。
    // 线程池（ExecutorService）复用线程避免频繁创建销毁的开销。
    // CompletableFuture提供链式异步编程，支持thenApply/thenCompose/exceptionally。
    // 并发工具：CountDownLatch（等待计数）、CyclicBarrier（同步屏障）、Semaphore（信号量）。
    static void exercise5() throws Exception {
        System.out.println("===== 第5题：并发编程 =====");

        // 1. Thread + Runnable
        System.out.println("--- 1. Thread与Runnable ---");
        Thread t1 = new Thread(() -> {
            System.out.println("  [线程] " + Thread.currentThread().getName() + " 运行中");
        }, "工作线程-1");
        t1.start();
        t1.join();  // 等待线程结束
        System.out.println("  线程状态: " + t1.getState());

        // 2. ReentrantLock
        System.out.println("--- 2. ReentrantLock ---");
        ReentrantLock lock = new ReentrantLock();
        int[] counter = {0};
        ExecutorService exec = Executors.newFixedThreadPool(3);
        for (int i = 0; i < 3; i++) {
            exec.submit(() -> {
                lock.lock();
                try {
                    for (int j = 0; j < 100; j++) counter[0]++;
                } finally {
                    lock.unlock();  // 必须在finally中释放
                }
            });
        }
        exec.shutdown();
        exec.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("  3线程各加100, 计数器 = " + counter[0] + " (应为300)");

        // 3. synchronized关键字
        System.out.println("--- 3. synchronized ---");
        final Object monitor = new Object();
        int[] syncCounter = {0};
        ExecutorService exec2 = Executors.newFixedThreadPool(3);
        for (int i = 0; i < 3; i++) {
            exec2.submit(() -> {
                synchronized (monitor) {
                    for (int j = 0; j < 100; j++) syncCounter[0]++;
                }
            });
        }
        exec2.shutdown();
        exec2.awaitTermination(5, TimeUnit.SECONDS);
        System.out.println("  synchronized计数器 = " + syncCounter[0] + " (应为300)");

        // 4. CompletableFuture
        System.out.println("--- 4. CompletableFuture ---");
        CompletableFuture<String> future = CompletableFuture
            .supplyAsync(() -> {
                try { Thread.sleep(100); } catch (InterruptedException e) {}
                return "异步计算完成";
            })
            .thenApply(s -> "结果: " + s)
            .thenApply(String::toUpperCase);
        System.out.println("  " + future.get());

        // 多个Future组合
        CompletableFuture<Integer> f1 = CompletableFuture.supplyAsync(() -> 10);
        CompletableFuture<Integer> f2 = CompletableFuture.supplyAsync(() -> 20);
        CompletableFuture<Integer> combined = f1.thenCombine(f2, Integer::sum);
        System.out.println("  10 + 20 = " + combined.get());

        // 5. CountDownLatch
        System.out.println("--- 5. CountDownLatch ---");
        int taskCount = 3;
        CountDownLatch latch = new CountDownLatch(taskCount);
        ExecutorService exec3 = Executors.newFixedThreadPool(taskCount);
        for (int i = 0; i < taskCount; i++) {
            final int taskId = i + 1;
            exec3.submit(() -> {
                System.out.println("  任务" + taskId + "完成");
                latch.countDown();
            });
        }
        latch.await();  // 等待所有任务完成
        System.out.println("  所有任务已完成");
        exec3.shutdown();

        // 思考题：CompletableFuture与Future有什么区别？
        // 提示：Future只能阻塞get()，CompletableFuture支持链式回调、组合、异常处理。
        System.out.println();
    }

    // ===== 第6题：异常处理 =====
    // 知识点：
    // Java异常分为Checked（编译期检查，必须处理）和Unchecked（运行时，可选处理）。
    // Checked异常继承Exception，Unchecked异常继承RuntimeException。
    // try-with-resources（Java 7+）自动关闭实现AutoCloseable的资源。
    // finally块无论是否异常都会执行（除非System.exit()）。
    // 自定义异常应提供有意义的构造器和消息。
    static void exercise6() throws Exception {
        System.out.println("===== 第6题：异常处理 =====");

        // 1. Checked异常
        System.out.println("--- 1. Checked异常（必须处理）---");
        try {
            withdraw(100, 200);  // 余额100，取200
        } catch (InsufficientFundsException e) {
            System.out.println("  捕获Checked异常: " + e.getMessage());
        }

        // 2. Unchecked异常
        System.out.println("--- 2. Unchecked异常（运行时）---");
        try {
            int[] arr = {1, 2, 3};
            System.out.println("  尝试访问arr[5]...");
            int val = arr[5];  // ArrayIndexOutOfBoundsException
            System.out.println("  值: " + val);
        } catch (ArrayIndexOutOfBoundsException e) {
            System.out.println("  捕获: " + e.getClass().getSimpleName());
        }

        // 3. 多重catch（Java 7+ 多异常合并）
        System.out.println("--- 3. 多重catch ---");
        try {
            String s = null;
            s.length();  // NullPointerException
        } catch (NullPointerException e) {
            System.out.println("  捕获空指针: " + e.getClass().getSimpleName());
        } catch (Exception e) {
            System.out.println("  捕获其他异常: " + e.getClass().getSimpleName());
        }

        // 4. try-with-resources
        System.out.println("--- 4. try-with-resources ---");
        try (ResourceFile res = new ResourceFile("config.txt")) {
            System.out.println("  使用资源中...");
            // 资源会在try块结束后自动调用close()
        }
        System.out.println("  (资源已自动关闭)");

        // 多资源
        System.out.println("--- 4b. 多资源 ---");
        try (ResourceFile r1 = new ResourceFile("file1.txt");
             ResourceFile r2 = new ResourceFile("file2.txt")) {
            System.out.println("  使用两个资源...");
        }

        // 5. finally块
        System.out.println("--- 5. finally块 ---");
        try {
            System.out.println("  try块执行");
            throw new RuntimeException("测试finally");
        } catch (RuntimeException e) {
            System.out.println("  catch块: " + e.getMessage());
        } finally {
            System.out.println("  finally块总是执行");
        }

        // 6. 异常链
        System.out.println("--- 6. 异常链 ---");
        try {
            try {
                throw new Exception("底层原因");
            } catch (Exception e) {
                throw new RuntimeException("上层异常", e);  // 保留原因
            }
        } catch (RuntimeException e) {
            System.out.println("  外层: " + e.getMessage());
            System.out.println("  原因: " + e.getCause().getMessage());
        }

        // 思考题：try-with-resources中如果close()也抛出异常，会发生什么？
        // 提示：close()的异常会被addSuppressed附加到主异常上，可通过getSuppressed获取。
        System.out.println();
    }

    // ===== 第7题：JVM基础 =====
    // 知识点：
    // JVM内存区域：堆（对象实例）、栈（方法栈帧）、方法区（类信息）、本地方法栈、程序计数器。
    // 垃圾回收（GC）：自动管理堆内存，主要回收不再被引用的对象。
    // GC算法：标记-清除、复制、标记-整理；分代收集（新生代/老年代）。
    // 类加载机制：双亲委派模型（引导→扩展→应用类加载器）。
    // 常用JVM参数：-Xms（初始堆）、-Xmx（最大堆）、-Xmn（新生代）。
    static void exercise7() {
        System.out.println("===== 第7题：JVM基础 =====");

        // 1. 内存信息
        System.out.println("--- 1. JVM内存信息 ---");
        Runtime rt = Runtime.getRuntime();
        System.out.println("  最大内存(maxMemory): " + rt.maxMemory() / 1024 / 1024 + " MB");
        System.out.println("  已分配内存(totalMemory): " + rt.totalMemory() / 1024 / 1024 + " MB");
        System.out.println("  空闲内存(freeMemory): " + rt.freeMemory() / 1024 / 1024 + " MB");
        System.out.println("  已使用内存: " + (rt.totalMemory() - rt.freeMemory()) / 1024 + " KB");
        System.out.println("  可用处理器: " + rt.availableProcessors());

        // 2. 垃圾回收演示
        System.out.println("--- 2. 垃圾回收演示 ---");
        long beforeMem = rt.totalMemory() - rt.freeMemory();
        // 创建大量临时对象（成为垃圾）
        for (int i = 0; i < 100000; i++) {
            String temp = new String("临时对象" + i);
        }
        long afterAlloc = rt.totalMemory() - rt.freeMemory();
        System.out.println("  分配前使用: " + beforeMem / 1024 + " KB");
        System.out.println("  分配后使用: " + afterAlloc / 1024 + " KB");

        System.gc();  // 建议JVM进行垃圾回收（不保证立即执行）
        try { Thread.sleep(100); } catch (InterruptedException e) {}
        long afterGC = rt.totalMemory() - rt.freeMemory();
        System.out.println("  GC后使用: " + afterGC / 1024 + " KB");
        System.out.println("  (System.gc()只是建议，JVM自行决定是否回收)");

        // 3. 类加载器层次
        System.out.println("--- 3. 类加载器层次 ---");
        ClassLoader appLoader = JavaExercises.class.getClassLoader();
        System.out.println("  应用类加载器: " + appLoader);
        if (appLoader != null) {
            System.out.println("  父加载器(扩展): " + appLoader.getParent());
            if (appLoader.getParent() != null) {
                System.out.println("  根加载器(引导): " + appLoader.getParent().getParent());
                System.out.println("  (引导类加载器通常返回null，由C++实现)");
            }
        }

        // 4. JVM系统属性
        System.out.println("--- 4. JVM系统属性 ---");
        System.out.println("  Java版本: " + System.getProperty("java.version"));
        System.out.println("  Java供应商: " + System.getProperty("java.vendor"));
        System.out.println("  JVM名称: " + System.getProperty("java.vm.name"));
        System.out.println("  操作系统: " + System.getProperty("os.name")
            + " " + System.getProperty("os.arch"));
        System.out.println("  用户目录: " + System.getProperty("user.dir"));

        // 5. finalize方法（已废弃，仅演示概念）
        System.out.println("--- 5. 对象生命周期 ---");
        System.out.println("  创建 → 使用 → 不可达 → GC标记 → finalize(已废弃) → 回收");
        System.out.println("  (Java 9+标记finalize为Deprecated，推荐try-with-resources)");

        // 思考题：为什么System.gc()只是"建议"而不是"强制"垃圾回收？
        // 提示：JVM有自己的GC策略和时机判断，强制GC可能影响性能。
        System.out.println();
    }

    // ===== 第8题：注解与反射 =====
    // 知识点：
    // 注解（Annotation）是元数据，不影响代码逻辑，可被反射读取。
    // 元注解：@Retention（保留策略）、@Target（作用目标）、@Inherited（继承）。
    // 反射API：Class对象获取类信息，Method/Field/Constructor操作成员。
    // 动态代理：Proxy.newProxyInstance运行时生成代理类，实现AOP。
    // 应用场景：框架（Spring IOC/AOP）、ORM映射、单元测试、序列化。
    static void exercise8() {
        System.out.println("===== 第8题：注解与反射 =====");

        // 1. 反射获取类信息
        System.out.println("--- 1. 反射获取类信息 ---");
        Class<?> clazz = GreetingImpl.class;
        System.out.println("  类名: " + clazz.getName());
        System.out.println("  简单名: " + clazz.getSimpleName());

        // 获取所有方法
        System.out.println("  方法列表:");
        for (Method m : clazz.getDeclaredMethods()) {
            System.out.println("    " + m.getName()
                + " - 参数数: " + m.getParameterCount());
        }

        // 2. 读取方法注解
        System.out.println("--- 2. 读取注解 ---");
        try {
            Method method = clazz.getMethod("sayHello", String.class);
            if (method.isAnnotationPresent(MyLog.class)) {
                MyLog log = method.getAnnotation(MyLog.class);
                System.out.println("  找到@MyLog注解, value = \"" + log.value() + "\"");
            }
        } catch (NoSuchMethodException e) {
            System.out.println("  方法未找到");
        }

        // 3. 反射调用方法
        System.out.println("--- 3. 反射调用方法 ---");
        try {
            Object instance = clazz.getDeclaredConstructor().newInstance();
            Method method = clazz.getMethod("sayHello", String.class);
            method.invoke(instance, "Reflection");
        } catch (Exception e) {
            System.out.println("  反射异常: " + e.getMessage());
        }

        // 4. 反射操作字段
        System.out.println("--- 4. 反射操作字段 ---");
        try {
            Person p = new Person("Test", 20, "北京");
            Field nameField = Person.class.getDeclaredField("name");
            nameField.setAccessible(true);  // 访问private字段
            System.out.println("  原name: " + nameField.get(p));
            nameField.set(p, "Modified");
            System.out.println("  修改后name: " + nameField.get(p));
        } catch (Exception e) {
            System.out.println("  字段操作异常: " + e.getMessage());
        }

        // 5. 动态代理
        System.out.println("--- 5. 动态代理 ---");
        GreetingService proxy = (GreetingService) Proxy.newProxyInstance(
            GreetingService.class.getClassLoader(),
            new Class[]{GreetingService.class},
            new LogHandler(new GreetingImpl())
        );
        proxy.sayHello("Proxy World");

        // 6. 自定义注解应用：简易AOP
        System.out.println("--- 6. 注解+反射 = 简易AOP ---");
        System.out.println("  (扫描@MyLog注解，自动添加日志)");
        System.out.println("  (Spring AOP的底层原理就是动态代理+注解)");

        // 思考题：反射会破坏封装性吗？什么时候应该避免使用反射？
        // 提示：反射可访问private成员，破坏封装。性能较差，应避免在热路径使用。
        System.out.println();
    }

    // ===== 第9题：Lambda与方法引用 =====
    // 知识点：
    // Lambda是Java 8引入的匿名函数，本质是函数式接口的实现。
    // 函数式接口：只有一个抽象方法的接口（@FunctionalInterface）。
    // 方法引用是Lambda的简写：类名::方法名、对象::方法名、类名::new。
    // 常用函数式接口：Function<T,R>、Predicate<T>、Consumer<T>、Supplier<T>。
    static void exercise9() {
        System.out.println("===== 第9题：Lambda与方法引用 =====");

        // 1. Lambda各种形式
        System.out.println("--- 1. Lambda表达式 ---");

        // 无参数（Runnable）
        Runnable r = () -> System.out.println("  无参数Lambda");
        r.run();

        // 单参数（Function）
        Function<String, Integer> strLen = s -> s.length();
        System.out.println("  'Hello'的长度: " + strLen.apply("Hello"));

        // 多参数（BiFunction）
        BiFunction<Integer, Integer, Integer> adder = (a, b) -> a + b;
        System.out.println("  3 + 5 = " + adder.apply(3, 5));

        // 块语句Lambda
        Function<Integer, String> classifier = n -> {
            if (n > 0) return "正数";
            else if (n < 0) return "负数";
            else return "零";
        };
        System.out.println("  -5的分类: " + classifier.apply(-5));
        System.out.println("  0的分类: " + classifier.apply(0));

        // 2. 方法引用
        System.out.println("--- 2. 方法引用 ---");

        // 静态方法引用（类名::静态方法）
        Function<String, Integer> parser = Integer::parseInt;
        System.out.println("  解析'42': " + parser.apply("42"));

        // 实例方法引用（对象::方法）
        String prefix = "Hello, ";
        Function<String, String> greeter = prefix::concat;
        System.out.println("  拼接: " + greeter.apply("World"));

        // 类的实例方法引用（类名::实例方法）
        // 第一个参数成为方法的接收者
        Function<String, String> upper = String::toUpperCase;
        System.out.println("  大写: " + upper.apply("hello"));

        // 构造方法引用（类名::new）
        Function<String, StringBuilder> sbCreator = StringBuilder::new;
        StringBuilder sb = sbCreator.apply("构造方法引用");
        System.out.println("  StringBuilder: " + sb.toString());

        // 3. 常用函数式接口
        System.out.println("--- 3. 常用函数式接口 ---");

        // Predicate：断言（返回boolean）
        Predicate<String> isEmpty = String::isEmpty;
        System.out.println("  'abc'为空: " + isEmpty.test("abc"));
        System.out.println("  ''为空: " + isEmpty.test(""));

        // Predicate组合
        Predicate<Integer> gt10 = n -> n > 10;
        Predicate<Integer> lt100 = n -> n < 100;
        Predicate<Integer> range = gt10.and(lt100);
        System.out.println("  50在10~100之间: " + range.test(50));

        // Consumer：消费（无返回值）
        Consumer<String> printer = s -> System.out.println("  消费: " + s);
        printer.accept("Hello Consumer");

        // Supplier：供给（无参数有返回）
        Supplier<Double> random = Math::random;
        System.out.println("  随机数: " + String.format("%.4f", random.get()));

        // 4. Lambda与集合
        System.out.println("--- 4. Lambda与集合 ---");
        List<String> names = Arrays.asList("Alice", "Bob", "Charlie", "David");

        // forEach + Lambda
        System.out.println("  Lambda遍历:");
        names.forEach(name -> System.out.println("    名字: " + name));

        // 方法引用简化
        System.out.println("  方法引用遍历:");
        names.forEach(System.out::println);

        // 5. 闭包捕获
        System.out.println("--- 5. 闭包捕获 ---");
        int base = 10;  // effectively final
        Function<Integer, Integer> addBase = x -> x + base;
        // base = 20;  // 错误：Lambda捕获的变量必须effectively final
        System.out.println("  addBase(5) = " + addBase.apply(5) + " (捕获base=10)");

        // 思考题：方法引用 String::compareTo 和 (s1, s2) -> s1.compareTo(s2) 等价吗？
        // 提示：等价。类的实例方法引用中，第一个参数成为接收者。
        System.out.println();
    }

    // ===== 第10题：设计模式实战 =====
    // 知识点：
    // 设计模式是前人总结的面向对象设计经验，分为创建型、结构型、行为型三大类。
    // 单例模式：确保全局唯一实例（枚举实现最安全，防反射防序列化）。
    // 工厂模式：封装对象创建逻辑，客户端不关心具体类。
    // 策略模式：将算法封装为独立策略，运行时可切换。
    // 观察者模式：一对多依赖，状态变化时自动通知所有观察者。
    // 装饰器模式：动态添加功能，比继承更灵活（替代多重继承）。
    static void exercise10() {
        System.out.println("===== 第10题：设计模式实战 =====");

        // 1. 单例模式（枚举实现，线程安全）
        System.out.println("--- 1. 单例模式（枚举实现）---");
        Singleton s1 = Singleton.INSTANCE;
        Singleton s2 = Singleton.INSTANCE;
        s1.setValue(42);
        System.out.println("  s1 == s2: " + (s1 == s2));
        System.out.println("  value = " + s2.getValue() + " (s1设置，s2读取)");
        System.out.println("  (枚举单例天然线程安全，防反射防序列化)");

        // 2. 工厂模式
        System.out.println("--- 2. 工厂模式 ---");
        Pet dog = PetFactory.create("dog");
        Pet cat = PetFactory.create("cat");
        System.out.print("  dog: "); dog.speak();
        System.out.print("  cat: "); cat.speak();
        System.out.println("  (客户端只需知道类型字符串，不关心具体类)");

        // 3. 策略模式
        System.out.println("--- 3. 策略模式 ---");
        int[] data1 = {5, 2, 8, 1, 9, 3, 7, 4, 6, 0};
        int[] data2 = data1.clone();

        ArraySorter sorter = new ArraySorter();
        sorter.setStrategy(new BubbleSort());
        sorter.sort(data1);

        sorter.setStrategy(new QuickSort());
        sorter.sort(data2);

        System.out.println("  (运行时切换排序算法，无需修改Sorter代码)");

        // 4. 观察者模式
        System.out.println("--- 4. 观察者模式 ---");
        NewsSubject publisher = new NewsSubject();
        NewsReader reader1 = new NewsReader("读者A");
        NewsReader reader2 = new NewsReader("读者B");
        publisher.subscribe(reader1);
        publisher.subscribe(reader2);
        publisher.publish("C++17正式发布！");
        publisher.unsubscribe(reader1);
        publisher.publish("Java 21 LTS发布！");
        System.out.println("  (读者A退订后不再收到消息)");

        // 5. 装饰器模式
        System.out.println("--- 5. 装饰器模式 ---");
        Coffee coffee = new BasicCoffee();
        System.out.println("  " + coffee.getDescription() + " - ￥" + coffee.cost());

        coffee = new MilkDecorator(coffee);
        System.out.println("  " + coffee.getDescription() + " - ￥" + coffee.cost());

        coffee = new SugarDecorator(coffee);
        System.out.println("  " + coffee.getDescription() + " - ￥" + coffee.cost());

        // 另一种组合
        Coffee coffee2 = new SugarDecorator(new MilkDecorator(new BasicCoffee()));
        System.out.println("  " + coffee2.getDescription() + " - ￥" + coffee2.cost());
        System.out.println("  (装饰器可任意组合，比继承更灵活)");

        // 思考题：装饰器模式和继承有什么区别？为什么说装饰器更灵活？
        // 提示：继承是编译期静态确定，装饰器是运行期动态组合，可任意叠加。
        System.out.println();
    }

    // ============================================================
    // 主方法
    // ============================================================
    public static void main(String[] args) throws Exception {
        System.out.println("========================================");
        System.out.println("  Java 进阶编程练习 - 10题");
        System.out.println("  创建日期：2026-08-05");
        System.out.println("========================================");
        System.out.println();

        exercise1();
        exercise2();
        exercise3();
        exercise4();
        exercise5();
        exercise6();
        exercise7();
        exercise8();
        exercise9();
        exercise10();

        System.out.println("========================================");
        System.out.println("  全部练习完成！");
        System.out.println("========================================");
    }
}
