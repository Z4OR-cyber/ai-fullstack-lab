#!/usr/bin/perl
use strict;
use warnings;
use utf8;
binmode(STDOUT, ":utf8");

# ============================================================
# 阶段：脚本语言与系统级语言扩展练习
# 语言：Perl
# 题数：3题
# 创建日期：2026-08-05
# ============================================================

# ============================================================
# 第1题：Perl基础（标量 / 数组 / 哈希 / 正则）
# ============================================================

# 【知识点讲解】
# Perl的变量有三种基本类型，通过sigil（变量前缀符号）区分：
# $scalar - 标量，存储单个值（数字、字符串、引用）
# @array  - 数组，有序列表
# %hash   - 哈希，键值对集合
# Perl的正则表达式是其最强大的特性之一，语法被许多语言借鉴。
# use strict 和 use warnings 是现代Perl的最佳实践。

# 1. 标量操作
my $name = "Perl学习者";
my $age = 25;
my $pi = 3.14159265;

# 字符串操作
my $greeting = "你好，" . $name . "！";  # 字符串连接用 .
my $repeat = "Ab" x 3;                    # 字符串重复用 x
print "标量:\n";
print "  greeting = $greeting\n";
print "  repeat = $repeat\n";

# 数字运算
my $sum = $age + $pi;
printf("  age + pi = %.2f\n", $sum);

# 2. 数组操作
my @colors = ("红", "绿", "蓝", "黄", "紫");
print "数组:\n";
print "  元素数: " . scalar(@colors) . "\n";  # scalar上下文获取长度
print "  第一个: $colors[0]\n";                # 数组索引从0开始
print "  最后一个: $colors[-1]\n";             # 负索引从末尾开始

# 数组切片
my @subset = @colors[1, 3];  # 获取索引1和3的元素
print "  切片[1,3]: @subset\n";

# 数组操作函数
push(@colors, "橙");         # 末尾添加
unshift(@colors, "白");      # 头部添加
my $last = pop(@colors);     # 末尾移除
my $first = shift(@colors);  # 头部移除
print "  操作后: @colors (弹出: $last, 移出: $first)\n";

# 遍历数组
print "  遍历: ";
foreach my $color (@colors) {
    print "$color ";
}
print "\n";

# 3. 哈希操作
my %person = (
    name  => "张三",
    age   => 30,
    city  => "上海",
    email => "zhangsan\@example.com",  # @需要转义
);
print "哈希:\n";
print "  姓名: $person{name}\n";
print "  城市: $person{city}\n";

# 添加/修改键值对
$person{phone} = "13800138000";

# 判断键是否存在
if (exists $person{email}) {
    print "  邮箱存在: $person{email}\n";
}

# 遍历哈希
while (my ($key, $value) = each %person) {
    print "  $key => $value\n";
}

# 获取所有键和值
my @keys = keys %person;
my @values = values %person;
print "  键数: " . scalar(@keys) . "\n";

# 4. 正则表达式基础
print "正则表达式:\n";

# 匹配
my $text = "Hello World 2026";
if ($text =~ /World/) {
    print "  匹配到 'World'\n";
}

# 捕获分组
if ($text =~ /(\w+)\s+(\w+)\s+(\d+)/) {
    print "  捕获: $1, $2, $3\n";
}

# 替换
my $sentence = "I love Java and Java is great";
$sentence =~ s/Java/Perl/g;  # 全局替换
print "  替换后: $sentence\n";

# 字符类与量词
my @emails = ("user\@test.com", "invalid-email", "admin\@site.org");
foreach my $email (@emails) {
    if ($email =~ /^[\w.]+\@[\w.]+\.\w+$/) {
        print "  有效邮箱: $email\n";
    } else {
        print "  无效邮箱: $email\n";
    }
}

# 【思考题】
# 1. Perl中 scalar 上下文和 list 上下文的区别是什么？举例说明同一表达式在两种上下文中的不同行为。
# 2. my、our、local 三种变量声明有什么区别？

# ============================================================
# 第2题：引用与数据结构（匿名数组 / 哈希 / 嵌套）
# ============================================================

# 【知识点讲解】
# Perl的引用类似于C的指针或Python的引用，指向其他数据。
# 引用使Perl能够构建复杂的数据结构：数组的数组、哈希的数组等。
# 匿名数组用 [ ] 创建，匿名哈希用 { } 创建。
# 箭头操作符 -> 用于解引用访问嵌套元素。

# 1. 标量引用
my $value = 42;
my $ref = \$value;       # 取引用
print "引用:\n";
print "  原值: $value\n";
print "  解引用: $$ref\n";     # $$ref 解引用标量
$$ref = 100;                    # 通过引用修改原值
print "  修改后: $value\n";

# 2. 数组引用与匿名数组
my @nums = (1, 2, 3);
my $arr_ref = \@nums;           # 取数组引用
my $anon_arr = [4, 5, 6];      # 匿名数组引用

print "  数组引用第一个元素: $arr_ref->[0]\n";
print "  匿名数组: @$anon_arr\n";  # @{...} 解引用整个数组

# 3. 哈希引用与匿名哈希
my %config = (host => "localhost", port => 8080);
my $hash_ref = \%config;
my $anon_hash = {               # 匿名哈希
    name => "配置项",
    enabled => 1,
    options => {                # 嵌套匿名哈希
        debug => 1,
        verbose => 0,
    },
};

print "  host: $hash_ref->{host}\n";
print "  嵌套debug: $anon_hash->{options}{debug}\n";

# 4. 构建复杂数据结构：数组中的哈希（类似JSON数组）
my @students = (
    { name => "张三", score => 85, subjects => ["数学", "物理"] },
    { name => "李四", score => 92, subjects => ["化学", "生物"] },
    { name => "王五", score => 78, subjects => ["语文", "英语"] },
);

print "学生数据:\n";
foreach my $student (@students) {
    my $subjects_str = join(", ", @{$student->{subjects}});
    printf("  %s: %d分, 科目: %s\n",
        $student->{name},
        $student->{score},
        $subjects_str
    );
}

# 5. 哈希中的数组（分组数据）
my %grouped = (
    frontend => ["HTML", "CSS", "JavaScript"],
    backend  => ["Perl", "PHP", "Python"],
    database => ["MySQL", "Redis"],
);

print "技术分组:\n";
foreach my $category (sort keys %grouped) {
    my $techs = join(", ", @{$grouped{$category}});
    print "  $category: $techs\n";
}

# 6. 二维数组（矩阵）
my $matrix = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
];

print "矩阵转置:\n";
for my $i (0 .. $#{$matrix->[0]}) {
    for my $j (0 .. $#{$matrix}) {
        print "$matrix->[$j][$i] ";
    }
    print "\n";
}

# 7. 深层解引用技巧
my $data = {
    users => [
        { name => "A", tags => ["admin", "active"] },
        { name => "B", tags => ["user"] },
    ],
};

# 获取第一个用户的第二个标签
my $tag = $data->{users}[0]{tags}[1];
print "深层访问: $tag\n";

# 【思考题】
# 1. $$ref、@{$ref}、$ref->[0] 三种解引用方式的适用场景分别是什么？
# 2. 如何实现深拷贝（deep copy）一个包含嵌套引用的Perl数据结构？

# ============================================================
# 第3题：文本处理与正则实战（捕获 / 替换 / split / 文件处理）
# ============================================================

# 【知识点讲解】
# Perl被誉为"文本处理的瑞士军刀"，在日志分析、数据清洗等领域应用广泛。
# 核心能力包括：正则捕获与反向引用、替换修饰符、split/join、文件读写。
# Perl的文件操作简单直接：open打开文件句柄，<>读取行。

# 1. 正则捕获与命名捕获
my $log_line = '2026-08-05 14:30:22 [ERROR] user=alice action=login ip=192.168.1.100';

# 命名捕获
if ($log_line =~ /(?<date>\d{4}-\d{2}-\d{2})\s+(?<time>\d{2}:\d{2}:\d{2})\s+\[(?<level>\w+)\]\s+user=(?<user>\w+)\s+action=(?<action>\w+)\s+ip=(?<ip>[\d.]+)/) {
    print "日志解析:\n";
    print "  日期: $+{date}\n";
    print "  时间: $+{time}\n";
    print "  级别: $+{level}\n";
    print "  用户: $+{user}\n";
    print "  动作: $+{action}\n";
    print "  IP: $+{ip}\n";
}

# 2. 正则替换实战：格式转换
my $csv_data = "姓名,年龄,城市\n张三,25,北京\n李四,30,上海\n王五,28,广州";
print "\nCSV转JSON:\n";

# split按行分割
my @lines = split(/\n/, $csv_data);
my @headers = split(/,/, shift @lines);  # 第一行是表头

my @records;
foreach my $line (@lines) {
    my @fields = split(/,/, $line);
    my %record;
    @record{@headers} = @fields;  # 哈希切片：批量赋值
    push @records, \%record;
}

# 手动构建JSON字符串（不依赖外部模块）
my $json = "[\n";
for my $i (0 .. $#records) {
    $json .= "  {";
    my @pairs;
    for my $key (keys %{$records[$i]}) {
        push @pairs, "\"$key\": \"$records[$i]{$key}\"";
    }
    $json .= join(", ", @pairs);
    $json .= "}";
    $json .= "," if $i < $#records;
    $json .= "\n";
}
$json .= "]";
print $json, "\n";

# 3. 高级正则：前瞻与后顾
my $text2 = "price: \$100, \$200, and \$350 total";

# 捕获所有价格
my @prices = $text2 =~ /\$(\d+)/g;
print "\n价格提取: @prices\n";

# 计算总价（不使用eval，逐个累加更安全）
my $total = 0;
$total += $_ for @prices;
print "总价: $total\n";

# 替换：将价格增加10%
$text2 =~ s/\$(\d+)/sprintf("\$%d", $1 * 1.1)/ge;  # e修饰符执行代码
print "涨价后: $text2\n";

# 4. 文件处理示例
# 写入临时文件（云端可运行）
my $filename = "/tmp/perl_exercise_data.txt";

# 写入数据
open(my $fh_write, ">:utf8", $filename) or die "无法写入文件 $filename: $!";
print $fh_write "姓名,数学,语文,英语\n";
print $fh_write "张三,85,90,78\n";
print $fh_write "李四,92,88,95\n";
print $fh_write "王五,78,85,82\n";
close($fh_write);
print "\n文件已写入: $filename\n";

# 读取并处理
open(my $fh_read, "<:utf8", $filename) or die "无法读取文件 $filename: $!";
my @header = split(/,/, <$fh_read>);
chomp(@header);

print "成绩统计:\n";
while (my $line = <$fh_read>) {
    chomp $line;
    my @fields = split(/,/, $line);
    my $name = shift @fields;

    # 计算总分和平均分
    my $total_score = 0;
    $total_score += $_ for @fields;
    my $avg = $total_score / scalar(@fields);

    # 格式化输出
    printf("  %s: 总分=%d, 平均=%.1f\n", $name, $total_score, $avg);

    # 找出最高分科目
    my $max_idx = 0;
    for my $i (1 .. $#fields) {
        $max_idx = $i if $fields[$i] > $fields[$max_idx];
    }
    printf("    最佳科目: %s (%s分)\n", $header[$max_idx + 1], $fields[$max_idx]);
}
close($fh_read);

# 5. 正则修饰符总结
print "\n正则修饰符示例:\n";
# /i 不区分大小写
print "  /i: " . ("Hello" =~ /hello/i ? "匹配" : "不匹配") . "\n";
# /s 让.匹配换行
my $multi = "line1\nline2";
print "  /s: " . ($multi =~ /line1.line2/s ? "匹配" : "不匹配") . "\n";
# /x 允许注释和空白
my $regex = qr{
    ^           # 行首
    (\d{4})     # 年
    -           # 分隔符
    (\d{2})     # 月
    -           # 分隔符
    (\d{2})     # 日
    $           # 行尾
}x;
print "  /x: " . ("2026-08-05" =~ $regex ? "匹配" : "不匹配") . "\n";

# 清理临时文件
unlink $filename;

# 【思考题】
# 1. s///ge 中的 e 修饰符的作用是什么？在什么场景下特别有用？
# 2. 如果要处理一个10GB的日志文件，应该用什么方式读取以避免内存溢出？
