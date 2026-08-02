# my-skill

个人 Skill 收藏夹。根目录中的每个标准 Skill 都可以按目录单独安装；
[`registry.yaml`](registry.yaml) 记录外部来源、固定版本、许可证和导入方式。

## 本次收录的外部来源

- `devicelab-dev/maestro-runner`：收录项目级包装 Skill，固定 CLI `v1.1.22`。
- `cloudflare/skills`：收录 11 个可以独立安装的 Cloudflare Skills。
- `zhaoxuya520/reverse-skill`：完整保存强耦合套件，通过 `reverse-skill` 统一入口加载。
- `rorkai/App-Store-Connect-CLI`：收录官方配套仓库中固定审查版本的 23 个 ASC 工作流 Skills，对应 CLI `3.4.1`。

第三方许可证保存在 [`THIRD_PARTY_LICENSES`](THIRD_PARTY_LICENSES/)；
外部更新应先审查差异，再修改 `registry.yaml` 中的 commit。

## 安装

使用 Codex 自带的 GitHub Skill 安装脚本，可以安装一个或多个目录：

```bash
install-skill-from-github.py \
  --repo TwitterIsGood/my-skill \
  --path cloudflare wrangler reverse-skill
```

App Store Connect 工作流可以按需安装，例如：

```bash
install-skill-from-github.py \
  --repo TwitterIsGood/my-skill \
  --path asc-cli-usage asc-testflight-orchestration asc-release-flow
```

这些 ASC Skills 需要 `asc` CLI。macOS 推荐使用 `brew install asc`，并将
App Store Connect 私钥和凭据保存在现有密钥管理或 CLI 配置中，不要提交到仓库。

`maestro-runner` 设计为项目级 Skill。将它安装到目标项目的
`.agents/skills/maestro-runner`，再由包装脚本下载固定版本：

```bash
.agents/skills/maestro-runner/scripts/install.sh
.agents/skills/maestro-runner/scripts/run.sh --version
```

不要提交 `.tools/maestro-runner`、测试报告、设备凭据或签名材料。

## 收录规则

1. 固定上游 commit 或 release，不直接漂移跟踪最新代码。
2. 保留上游许可证和作者信息。
3. 导入前检查 `SKILL.md`、脚本、依赖、网络访问和凭据要求。
4. 强耦合套件保持完整目录结构，不拆成不可运行的碎片。
5. 上游更新通过独立提交或 PR 审查，不自动覆盖。
