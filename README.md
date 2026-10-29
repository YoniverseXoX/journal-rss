# 社会学期刊 RSS 生成器

为《社会学研究》《社会》《社会学评论》三本期刊生成 RSS 2.0 订阅源（非官方，数据抓自各期刊官网的当期目录页）。

## 订阅地址

部署到 GitHub Pages 后，三个订阅地址为（把 `<用户名>` 和 `<仓库名>` 换成你的）：

| 期刊 | Feed URL |
|---|---|
| 社会 | `https://<用户名>.github.io/<仓库名>/feeds/society-shu.xml` |
| 社会学评论 | `https://<用户名>.github.io/<仓库名>/feeds/sociological-review.xml` |
| 社会学研究 | `https://<用户名>.github.io/<仓库名>/feeds/sociological-studies.xml` |

## 部署步骤（一次性）

1. 在 GitHub 上新建一个**公开**仓库（不要勾选初始化 README）。
2. 推送本目录：
   ```bash
   git remote add origin git@github.com:<用户名>/<仓库名>.git
   git push -u origin main
   ```
3. 仓库页面 → **Settings → Pages → Build and deployment**，Source 选 **Deploy from a branch**，Branch 选 `main` / 根目录 `/`，保存。
4. 仓库页面 → **Actions**，手动运行一次 "Update journal RSS feeds" 验证（之后每天自动运行，约北京时间 09:17）。
5. 等 Pages 生效（约 1 分钟），把上面三个地址添加进 memomind 客户端的 RSS 订阅。

## 本地运行

```bash
python3 journal_rss.py            # 生成/更新 feeds/ 下的三个 XML
python3 journal_rss.py --no-abstract   # 跳过逐篇抓取摘要（更快）
```

只依赖 Python 3 标准库，无需安装任何包。重复运行会与已有 feed 合并，保留历史条目（每刊最多 60 条）。

## 数据来源

- 《社会》：https://www.society.shu.edu.cn/CN/current（含摘要、刊出日期）
- 《社会学评论》：http://src.ruc.edu.cn/CN/current（摘要取自各文章页）
- 《社会学研究》：https://shxyj.ajcass.com/（官网文章页有 JS 验证，仅含标题、作者、年期）

若官网改版导致解析失败，脚本会报错退出，feed 保留旧内容。
