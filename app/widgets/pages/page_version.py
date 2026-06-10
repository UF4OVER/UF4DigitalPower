# -*- coding: utf-8 -*-
# -------------------------------
#  @Project : F4CP
#  @Time    : 2026 - 06-06 20:00
#  @FileName: page_version.py
#  @FileType: 版本与固件管理页面，负责软件提交历史、远程固件历史和详情下载
#  @Software: PyCharm 2024.1.6 (Professional Edition)
#  @System  : Windows 11 23H2
#  @Author  : UF4
#  @Contact :
#  @Python  : 3.11
# -------------------------------

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from urllib.request import urlopen

from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon as FIF,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    StrongBodyLabel,
    TableWidget,
    TextEdit,
    TitleLabel,
    isDarkTheme,
    setFont,
)

from app.core.utility import showMessage
from app.core.update_request import build_request
from config import get_logger

logger = get_logger("VersionPage")

KIND_TEXT = {
    "Power": "电源固件",
    "Upper": "上位固件",
}
from app.manager import (
    FirmwareDetailFinishedEvent,
    FirmwareDownloadFinishedEvent,
    FirmwareHistoryFinishedEvent,
    FirmwareRelease,
    GithubAuthResult,
    GithubLoginThread,
    GithubLogoutThread,
    GithubSessionRefreshThread,
    StyleSheet,
    cached_session_state,
    firmware_download_manager,
    firmware_history_manager,
    update_manager,
)
from app.widgets.icon import UF4Icon
from config import CTX, REPO_URL, VERSION


@dataclass(frozen=True)
class GitCommitItem:
    short_hash: str
    date: str
    subject: str
    author: str


class GitCommitsThread(QThread):
    finished_signal = pyqtSignal(list)

    def __init__(self, limit: int = 40, parent=None):
        super().__init__(parent)
        self.limit = limit

    def run(self):
        url = f"https://api.github.com/repos/UF4OVER/UF4DigitalPower/commits?per_page={self.limit}"
        request = build_request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "F4CP-UpdateChecker",
            },
        )
        try:
            with urlopen(request, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8-sig"))

            commits = []
            if isinstance(data, list):
                for item in data:
                    sha = item.get("sha", "")
                    short_hash = sha[:7] if sha else "--"
                    commit_info = item.get("commit", {})
                    author_info = commit_info.get("author", {})

                    raw_date = author_info.get("date", "")
                    date_str = raw_date[:10] if len(raw_date) >= 10 else "--"

                    full_message = commit_info.get("message", "")
                    subject = full_message.split("\n")[0].strip() if full_message else "--"

                    author_name = author_info.get("name", "--")
                    commits.append({
                        "short_hash": short_hash,
                        "date": date_str,
                        "subject": subject,
                        "author": author_name
                    })
                self.finished_signal.emit(commits)
                return
        except Exception as e:
            logger.warning(f"Failed to fetch git commits online: {e}")

        self.finished_signal.emit([])


class VersionInfoCard(CardWidget):
    def __init__(self, title: str, value: str, caption: str, parent=None):
        super().__init__(parent)
        self.setObjectName("VersionInfoCard")
        self.titleLabel = CaptionLabel(title, self)
        self.valueLabel = BodyLabel(value, self)
        self.captionLabel = CaptionLabel(caption, self)
        self.captionLabel.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)
        layout.addWidget(self.titleLabel)
        layout.addWidget(self.valueLabel)
        layout.addWidget(self.captionLabel)

        setFont(self.valueLabel, 18, QFont.DemiBold)

    def setValue(self, value: str) -> None:
        self.valueLabel.setText(value or "--")


class SectionCard(CardWidget):
    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("VersionSectionCard")
        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.setContentsMargins(20, 18, 20, 20)
        self.vBoxLayout.setSpacing(12)

        header = QWidget(self)
        headerLayout = QVBoxLayout(header)
        headerLayout.setContentsMargins(0, 0, 0, 0)
        headerLayout.setSpacing(2)
        self.titleLabel = StrongBodyLabel(title, header)
        self.subtitleLabel = CaptionLabel(subtitle, header)
        self.subtitleLabel.setWordWrap(True)
        self.subtitleLabel.setVisible(bool(subtitle))
        headerLayout.addWidget(self.titleLabel)
        headerLayout.addWidget(self.subtitleLabel)
        self.vBoxLayout.addWidget(header)

    def addWidget(self, widget: QWidget, stretch: int = 0) -> None:
        self.vBoxLayout.addWidget(widget, stretch)

    def addLayout(self, layout, stretch: int = 0) -> None:
        self.vBoxLayout.addLayout(layout, stretch)


class VersionPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("VersionPage")
        self._remoteReleases: dict[str, list[FirmwareRelease]] = {"Power": [], "Upper": []}
        self._selectedRelease: FirmwareRelease | None = None
        self._detailRelease: FirmwareRelease | None = None
        self._detailChangelog = ""
        self._downloadingKinds: set[str] = set()
        self._githubLoginThread: GithubLoginThread | None = None
        self._githubRefreshThread: GithubSessionRefreshThread | None = None
        self._githubLogoutThread: GithubLogoutThread | None = None
        self._githubSessionChecked = False

        self.scrollWidget = QWidget(self)
        self.scrollWidget.setObjectName("versionScrollWidget")
        self.mainLayout = QVBoxLayout(self.scrollWidget)
        self.mainLayout.setContentsMargins(24, 24, 24, 24)
        self.mainLayout.setSpacing(16)

        self._initHeader()
        self._initSummary()
        self._initGithubAuthCard()
        self._initFirmwareCard()
        self._initSoftwareHistoryCard()

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._connectSignals()
        self._applyVersionSnapshot()
        self._reloadGitCommits()
        StyleSheet.VERSION_PAGE.apply(self)
        self._applyLocalStyle()
        self._loadCachedFirmwareHistory()

    def _initHeader(self) -> None:
        header = QWidget(self.scrollWidget)  # NOQA
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        titleBox = QWidget(header)
        titleLayout = QVBoxLayout(titleBox)
        titleLayout.setContentsMargins(0, 0, 0, 0)
        titleLayout.setSpacing(2)
        self.titleLabel = TitleLabel("版本与固件", titleBox)
        self.subtitleLabel = BodyLabel("查看软件提交历史，管理远程固件版本，并打开固件提交详情。", titleBox)
        titleLayout.addWidget(self.titleLabel)
        titleLayout.addWidget(self.subtitleLabel)

        self.openUpdateSiteButton = PushButton(FIF.LINK, "更新站点", header)
        self.openRepoButton = PushButton(UF4Icon.BOARD, "项目仓库", header)

        layout.addWidget(titleBox, 1)
        layout.addWidget(self.openUpdateSiteButton, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.openRepoButton, 0, Qt.AlignmentFlag.AlignTop)
        self.mainLayout.addWidget(header)

    def _initSummary(self) -> None:
        summary = QWidget(self.scrollWidget)
        layout = QGridLayout(summary)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.appVersionCard = VersionInfoCard("软件版本", VERSION, "当前运行的 F4CP 上位机版本", summary)
        self.powerVersionCard = VersionInfoCard("Power 固件", "--", "本地 / 远程最新版本", summary)
        self.upperVersionCard = VersionInfoCard("Upper 固件", "--", "本地 / 远程最新版本", summary)
        layout.addWidget(self.appVersionCard, 0, 0)
        layout.addWidget(self.powerVersionCard, 0, 1)
        layout.addWidget(self.upperVersionCard, 0, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        self.mainLayout.addWidget(summary)

    def _initFirmwareCard(self) -> None:
        self.firmwareCard = SectionCard(
            "远程固件",
            "从 https://update.hepi.ng 拉取固件索引；选择版本后可查看 manifest、changelog 和下载文件。",
            self.scrollWidget,
        )

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)
        self.kindCombo = ComboBox(self.firmwareCard)
        self.kindCombo.addItem("Power", userData="Power")
        self.kindCombo.addItem("Upper", userData="Upper")
        self.refreshFirmwareButton = PrimaryPushButton(FIF.SYNC, "刷新固件历史", self.firmwareCard)
        self.downloadFirmwareButton = PrimaryPushButton(FIF.DOWNLOAD, "下载选中版本", self.firmwareCard)
        self.downloadFirmwareButton.setEnabled(False)
        toolbar.addWidget(self.kindCombo)
        toolbar.addWidget(self.refreshFirmwareButton)
        toolbar.addStretch(1)
        toolbar.addWidget(self.downloadFirmwareButton)
        self.firmwareCard.addLayout(toolbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self.releaseTable = TableWidget(self.firmwareCard)
        self.releaseTable.setColumnCount(5)
        self.releaseTable.setHorizontalHeaderLabels(["版本", "日期", "通道", "推荐", "类型"])
        self.releaseTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.releaseTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.releaseTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.releaseTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.releaseTable.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.releaseTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.releaseTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.releaseTable.setMinimumHeight(300)

        detailPanel = QFrame(self.firmwareCard)
        detailPanel.setObjectName("FirmwareDetailPanel")
        detailLayout = QVBoxLayout(detailPanel)
        detailLayout.setContentsMargins(16, 14, 16, 16)
        detailLayout.setSpacing(10)
        self.detailTitleLabel = StrongBodyLabel("固件详情", detailPanel)
        self.detailMetaLabel = CaptionLabel("选择左侧版本后显示提交详情。", detailPanel)
        self.detailMetaLabel.setWordWrap(True)
        self.detailFileLabel = CaptionLabel("--", detailPanel)
        self.detailFileLabel.setWordWrap(True)
        self.changelogEdit = TextEdit(detailPanel)
        self.changelogEdit.setReadOnly(True)
        self.changelogEdit.setMinimumHeight(220)
        detailLayout.addWidget(self.detailTitleLabel)
        detailLayout.addWidget(self.detailMetaLabel)
        detailLayout.addWidget(self.detailFileLabel)
        detailLayout.addWidget(self.changelogEdit, 1)

        body.addWidget(self.releaseTable, 3)
        body.addWidget(detailPanel, 4)
        self.firmwareCard.addLayout(body)
        self.mainLayout.addWidget(self.firmwareCard)

    def _initGithubAuthCard(self) -> None:
        self.githubCard = SectionCard(
            "GitHub 登录",
            "登录 GitHub 后，当前账号访问更新站时会获得双倍请求额度；未登录时仍可访问，但额度为默认值。",
            self.scrollWidget,
        )

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        textBox = QWidget(self.githubCard)
        textLayout = QVBoxLayout(textBox)
        textLayout.setContentsMargins(0, 0, 0, 0)
        textLayout.setSpacing(4)
        self.githubStatusLabel = StrongBodyLabel("未登录", textBox)
        self.githubMetaLabel = CaptionLabel("登录后可获得双倍访问额度。", textBox)
        self.githubMetaLabel.setWordWrap(True)
        textLayout.addWidget(self.githubStatusLabel)
        textLayout.addWidget(self.githubMetaLabel)

        self.githubLoginButton = PrimaryPushButton(FIF.PEOPLE, "GitHub 登录", self.githubCard)
        self.githubRefreshButton = PushButton(FIF.SYNC, "刷新状态", self.githubCard)
        self.githubLogoutButton = PushButton(FIF.CLOSE, "退出登录", self.githubCard)

        row.addWidget(textBox, 1)
        row.addWidget(self.githubLoginButton)
        row.addWidget(self.githubRefreshButton)
        row.addWidget(self.githubLogoutButton)
        self.githubCard.addLayout(row)
        self.mainLayout.addWidget(self.githubCard)

    def _initSoftwareHistoryCard(self) -> None:
        self.softwareCard = SectionCard("软件提交", "读取当前项目 Git 历史，便于查看本软件最近的提交记录。", self.scrollWidget)
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(8)
        self.refreshCommitsButton = PushButton(FIF.SYNC, "刷新提交", self.softwareCard)
        toolbar.addStretch(1)
        toolbar.addWidget(self.refreshCommitsButton)
        self.softwareCard.addLayout(toolbar)

        self.commitTable = TableWidget(self.softwareCard)
        self.commitTable.setColumnCount(4)
        self.commitTable.setHorizontalHeaderLabels(["提交", "日期", "说明", "作者"])
        self.commitTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.commitTable.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.commitTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.commitTable.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.commitTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.commitTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.commitTable.setMinimumHeight(260)
        self.softwareCard.addWidget(self.commitTable)
        self.mainLayout.addWidget(self.softwareCard)

    def _connectSignals(self) -> None:
        self.openUpdateSiteButton.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self._firmwareBaseUrl())))
        self.openRepoButton.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(REPO_URL)))
        self.githubLoginButton.clicked.connect(self._startGithubLogin)
        self.githubRefreshButton.clicked.connect(lambda: self._refreshGithubSession(force=True))
        self.githubLogoutButton.clicked.connect(self._logoutGithub)
        self.kindCombo.currentIndexChanged.connect(self._populateReleaseTable)
        self.refreshFirmwareButton.clicked.connect(lambda: self.refreshFirmwareHistory(force_refresh=True))
        self.downloadFirmwareButton.clicked.connect(self.downloadSelectedFirmware)
        self.releaseTable.itemSelectionChanged.connect(self._onReleaseSelectionChanged)
        self.releaseTable.itemDoubleClicked.connect(lambda *_: self._loadSelectedReleaseDetail())
        self.refreshCommitsButton.clicked.connect(self._reloadGitCommits)

    def event(self, event):
        if event.type() == FirmwareHistoryFinishedEvent.EVENT_TYPE:
            self.refreshFirmwareButton.setEnabled(True)
            self._handleFirmwareHistoryResult(event.result)
            return True

        if event.type() == FirmwareDetailFinishedEvent.EVENT_TYPE:
            self._handleFirmwareDetailResult(event.result)
            return True

        if event.type() == FirmwareDownloadFinishedEvent.EVENT_TYPE:
            self._downloadingKinds.discard(event.result.kind)
            self.downloadFirmwareButton.setEnabled(self._detailRelease is not None)
            self._handleFirmwareDownloadResult(event.result)
            return True

        return super().event(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._applyVersionSnapshot()
        if not self._githubSessionChecked:
            self._applyGithubSessionSnapshot()
            self._refreshGithubSession(force=False)
            self._githubSessionChecked = True

    def _onThemeChanged(self, *_):
        StyleSheet.VERSION_PAGE.apply(self)
        self._applyLocalStyle()

    def _loadCachedFirmwareHistory(self) -> None:
        cached = firmware_history_manager.cached_history()
        if any(cached.values()):
            self._remoteReleases = {
                "Power": list(cached.get("Power", [])),
                "Upper": list(cached.get("Upper", [])),
            }
            self._populateReleaseTable()
            return

        self.refreshFirmwareHistory(force_refresh=True)

    def refreshFirmwareHistory(self, force_refresh: bool = False) -> None:
        if firmware_history_manager.is_refreshing:
            showMessage(self, "刷新中", "固件历史正在刷新。", "info")
            return

        self.refreshFirmwareButton.setEnabled(False)
        self.refreshFirmwareButton.setText("刷新中..." if force_refresh else "读取缓存...")
        started = firmware_history_manager.refresh_history(self, force_refresh=force_refresh)
        if not started:
            self.refreshFirmwareButton.setEnabled(True)
            self.refreshFirmwareButton.setText("刷新固件历史")

    def downloadSelectedFirmware(self) -> None:
        if self._detailRelease is None:
            showMessage(self, "未选择固件", "请先选择一个远程版本并加载详情。", "warning")
            return

        if firmware_download_manager.is_downloading(self._detailRelease.kind):
            showMessage(self, "下载中", "该类型固件已有下载任务。", "warning")
            return

        started = firmware_download_manager.download_release(self._detailRelease, self)
        if not started:
            return

        self._downloadingKinds.add(self._detailRelease.kind)
        self.downloadFirmwareButton.setEnabled(False)
        self.downloadFirmwareButton.setText("下载中...")

    def _handleFirmwareHistoryResult(self, result) -> None:
        self.refreshFirmwareButton.setText("刷新固件历史")
        if not result.success:
            showMessage(self, "固件历史刷新失败", result.message, "warning")
            return

        self._remoteReleases = {
            "Power": list(result.releases.get("Power", [])),
            "Upper": list(result.releases.get("Upper", [])),
        }
        self._populateReleaseTable()
        self._applyVersionSnapshot()
        showMessage(self, "固件历史已刷新", "远程固件索引已更新。", "success", autoCloseMs=2200)

    def _handleFirmwareDetailResult(self, result) -> None:
        if not result.success or result.release is None:
            self._detailRelease = None
            self.downloadFirmwareButton.setEnabled(False)
            self.detailMetaLabel.setText(result.message)
            self.changelogEdit.setPlainText("")
            showMessage(self, "固件详情加载失败", result.message, "warning")
            return

        self._detailRelease = result.release
        self._detailChangelog = result.changelog
        self._renderFirmwareDetail(result.release, result.changelog)
        self.downloadFirmwareButton.setEnabled(not firmware_download_manager.is_downloading(result.release.kind))

    def _handleFirmwareDownloadResult(self, result) -> None:
        self.downloadFirmwareButton.setText("下载选中版本")
        if result.success and result.release is not None:
            self._applyVersionSnapshot()
            showMessage(
                self,
                "固件下载完成",
                "{kind} 已下载到本地：{version}".format(
                    kind=KIND_TEXT.get(result.kind, result.kind),
                    version=result.release.version,
                ),
                "success",
            )
            return

        showMessage(self, "固件下载失败", result.message, "warning")

    def _populateReleaseTable(self) -> None:
        kind = self._currentKind()
        releases = self._remoteReleases.get(kind, [])
        self.releaseTable.setRowCount(0)
        self._selectedRelease = None
        self._detailRelease = None
        self.downloadFirmwareButton.setEnabled(False)
        self.detailTitleLabel.setText("固件详情")
        self.detailMetaLabel.setText("选择左侧版本后显示提交详情。")
        self.detailFileLabel.setText("--")
        self.changelogEdit.setPlainText("")

        for row, release in enumerate(releases):
            self.releaseTable.insertRow(row)
            values = [
                release.version,
                release.date or "--",
                release.channel or "--",
                "是" if getattr(release, "recommended", False) else "否",
                KIND_TEXT.get(release.kind, release.kind),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, release)
                self.releaseTable.setItem(row, column, item)

        if releases:
            self.releaseTable.selectRow(0)
        else:
            self.detailMetaLabel.setText("未找到远程固件历史。")

    def _onReleaseSelectionChanged(self) -> None:
        self._selectedRelease = self._releaseFromSelectedRow()
        self._loadSelectedReleaseDetail()

    def _loadSelectedReleaseDetail(self) -> None:
        release = self._selectedRelease or self._releaseFromSelectedRow()
        if release is None:
            return

        self._selectedRelease = release
        self._detailRelease = None
        self.downloadFirmwareButton.setEnabled(False)
        self.detailTitleLabel.setText(f"{KIND_TEXT.get(release.kind, release.kind)} {release.version}")
        self.detailMetaLabel.setText("正在加载 manifest 与 changelog...")
        self.detailFileLabel.setText("--")
        self.changelogEdit.setPlainText("")
        cached = firmware_history_manager.cached_detail(release.kind, release.version)
        if cached is not None:
            cached_release, changelog = cached
            self._detailRelease = cached_release
            self._detailChangelog = changelog
            self._renderFirmwareDetail(cached_release, changelog)
            self.downloadFirmwareButton.setEnabled(not firmware_download_manager.is_downloading(cached_release.kind))
            return

        firmware_history_manager.load_detail(release.kind, release.version, self)

    def _renderFirmwareDetail(self, release: FirmwareRelease, changelog: str) -> None:
        self.detailTitleLabel.setText(f"{KIND_TEXT.get(release.kind, release.kind)} {release.version}")
        self.detailMetaLabel.setText(
            "日期：{date} | 通道：{channel} | 设备：{device} | 硬件：{hardware}".format(
                date=release.date or "--",
                channel=release.channel or "--",
                device=release.device or "--",
                hardware=release.hardware or "--",
            )
        )
        size_text = self._formatSize(release.size)
        self.detailFileLabel.setText(
            "文件：{name} | 大小：{size}\nSHA-256：{sha}".format(
                name=release.asset_name or "--",
                size=size_text,
                sha=release.sha256 or "--",
            )
        )
        self.changelogEdit.setPlainText((changelog or "").strip() or "该版本未提供 changelog。")

    def _loadCachedGitCommits(self) -> list[GitCommitItem]:
        cache_file = CTX.dirs.ResourcesDir / "Cache" / "git_commits_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                commits = []
                for item in data:
                    commits.append(GitCommitItem(
                        short_hash=item.get("short_hash", "--"),
                        date=item.get("date", "--"),
                        subject=item.get("subject", "--"),
                        author=item.get("author", "--"),
                    ))
                return commits
            except Exception as e:
                logger.warning(f"Failed to load cached git commits: {e}")
        return []

    def _saveCachedGitCommits(self, commits: list[dict[str, str]]) -> None:
        cache_file = CTX.dirs.ResourcesDir / "Cache" / "git_commits_cache.json"
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(commits, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save git commits to cache: {e}")

    def _reloadGitCommits(self) -> None:
        # Load cache first to make it instant
        cached_commits = self._loadCachedGitCommits()
        if cached_commits:
            self._updateCommitsTable(cached_commits)
        else:
            # If no cache, try loading local git log immediately
            local_commits = self._readGitCommits()
            if local_commits:
                self._updateCommitsTable(local_commits)

        # Trigger async refresh from remote repository in background
        self._refreshGitCommitsAsync()

    def _updateCommitsTable(self, commits: list[GitCommitItem]) -> None:
        self.commitTable.setRowCount(0)
        for row, commit in enumerate(commits):
            self.commitTable.insertRow(row)
            values = [commit.short_hash, commit.date, commit.subject, commit.author]
            for column, value in enumerate(values):
                self.commitTable.setItem(row, column, QTableWidgetItem(value))

        if not commits:
            self.commitTable.insertRow(0)
            self.commitTable.setItem(0, 0, QTableWidgetItem("--"))
            self.commitTable.setItem(0, 1, QTableWidgetItem("--"))
            self.commitTable.setItem(0, 2, QTableWidgetItem("当前没有可用的 Git 提交历史。"))
            self.commitTable.setItem(0, 3, QTableWidgetItem("--"))

    def _refreshGitCommitsAsync(self) -> None:
        if hasattr(self, "_gitCommitThread") and self._gitCommitThread and self._gitCommitThread.isRunning():
            return

        self.refreshCommitsButton.setEnabled(False)
        self.refreshCommitsButton.setText("刷新中...")

        self._gitCommitThread = GitCommitsThread(limit=40)
        self._gitCommitThread.finished_signal.connect(self._onGitCommitsFetched)
        self._gitCommitThread.start()

    def _onGitCommitsFetched(self, commits: list[dict[str, str]]) -> None:
        self.refreshCommitsButton.setEnabled(True)
        self.refreshCommitsButton.setText("刷新提交")

        if commits:
            self._saveCachedGitCommits(commits)
            items = [
                GitCommitItem(
                    short_hash=c["short_hash"],
                    date=c["date"],
                    subject=c["subject"],
                    author=c["author"]
                )
                for c in commits
            ]
            self._updateCommitsTable(items)
            showMessage(self, "同步成功", "已同步并缓存最新的提交历史。", "success")
        else:
            # Fallback to local git log
            local_commits = self._readGitCommits()
            if local_commits:
                self._updateCommitsTable(local_commits)
                showMessage(self, "本地模式", "网络同步失败，已载入本地 Git 历史。", "info")
            else:
                cached = self._loadCachedGitCommits()
                if not cached:
                    self._updateCommitsTable([])
                showMessage(self, "更新失败", "无法同步远程历史，本地 Git 亦不可用。", "warning")

    @staticmethod
    def _readGitCommits(limit: int = 40) -> list[GitCommitItem]:
        command = [
            "git",
            "log",
            f"--max-count={limit}",
            "--date=short",
            "--pretty=format:%h%x1f%ad%x1f%s%x1f%an",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(CTX.dirs.BaseDir),
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6,
            )
        except Exception as e:
            logger.debug(f"Local git log check skipped: {e}")
            return []

        commits: list[GitCommitItem] = []
        for line in completed.stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) != 4:
                continue
            commits.append(GitCommitItem(parts[0], parts[1], parts[2], parts[3]))
        return commits

    def _applyVersionSnapshot(self) -> None:
        snapshot = update_manager.get_cached_versions()
        self.appVersionCard.setValue(snapshot.local_app_version or VERSION)
        self.powerVersionCard.setValue(f"{snapshot.local_lower_version or '--'} / {snapshot.latest_lower_version or '--'}")
        self.upperVersionCard.setValue(f"{snapshot.local_upper_version or '--'} / {snapshot.latest_upper_version or '--'}")

    def _applyGithubSessionSnapshot(self) -> None:
        session = cached_session_state()
        if session.authenticated:
            self.githubStatusLabel.setText(f"已登录: {session.display_name}")
            expiry_text = self._formatExpiry(session.expires_at)
            self.githubMetaLabel.setText(
                f"GitHub 账号: @{session.github_login or '--'} | 会话到期: {expiry_text} | 当前访问更新站可获得双倍额度。"
            )
            self.githubLoginButton.setText("重新登录")
            self.githubLogoutButton.setEnabled(True)
        else:
            self.githubStatusLabel.setText("未登录")
            self.githubMetaLabel.setText("登录 GitHub 后，刷新固件索引和下载文件会获得双倍访问额度。")
            self.githubLoginButton.setText("GitHub 登录")
            self.githubLogoutButton.setEnabled(False)
        self.githubRefreshButton.setEnabled(True)

    def _setGithubBusy(self, busy: bool, action_text: str = "") -> None:
        self.githubLoginButton.setEnabled(not busy)
        self.githubRefreshButton.setEnabled(not busy)
        self.githubLogoutButton.setEnabled(not busy and cached_session_state().authenticated)
        if busy and action_text:
            self.githubMetaLabel.setText(action_text)

    def _startGithubLogin(self) -> None:
        if self._githubLoginThread is not None and self._githubLoginThread.isRunning():
            showMessage(self, "登录进行中", "浏览器授权流程仍在进行，请先完成当前登录。", "info")
            return
        self._githubLoginThread = GithubLoginThread(self)
        self._githubLoginThread.authorizeUrlReady.connect(self._openGithubAuthorizeUrl)
        self._githubLoginThread.resultReady.connect(self._handleGithubLoginResult)
        self._githubLoginThread.finished.connect(self._cleanupGithubLoginThread)
        self._setGithubBusy(True, "正在请求 GitHub 授权地址，请稍候...")
        self._githubLoginThread.start()

    def _openGithubAuthorizeUrl(self, url: str) -> None:
        self.githubMetaLabel.setText("浏览器授权页已打开，请在 GitHub 完成登录与授权。")
        QDesktopServices.openUrl(QUrl(url))

    def _handleGithubLoginResult(self, result: GithubAuthResult) -> None:
        self._setGithubBusy(False)
        self._applyGithubSessionSnapshot()
        if result.success:
            showMessage(self, "GitHub 登录成功", "当前账号已绑定到更新站，后续请求可获得双倍额度。", "success")
        else:
            showMessage(self, "GitHub 登录失败", result.message, "warning")

    def _cleanupGithubLoginThread(self) -> None:
        if self._githubLoginThread is not None:
            self._githubLoginThread.deleteLater()
            self._githubLoginThread = None

    def _refreshGithubSession(self, force: bool = False) -> None:
        session = cached_session_state()
        if not session.session_token:
            self._applyGithubSessionSnapshot()
            return
        if self._githubRefreshThread is not None and self._githubRefreshThread.isRunning():
            return
        if not force and session.expires_at > int(time.time()) and session.github_login:
            self._applyGithubSessionSnapshot()
            return
        self._githubRefreshThread = GithubSessionRefreshThread(session.session_token, self)
        self._githubRefreshThread.resultReady.connect(self._handleGithubRefreshResult)
        self._githubRefreshThread.finished.connect(self._cleanupGithubRefreshThread)
        self._setGithubBusy(True, "正在校验 GitHub 登录状态...")
        self._githubRefreshThread.start()

    def _handleGithubRefreshResult(self, result: GithubAuthResult) -> None:
        self._setGithubBusy(False)
        self._applyGithubSessionSnapshot()
        if result.success:
            if result.session is not None:
                showMessage(self, "GitHub 状态已更新", f"当前登录账号：@{result.session.github_login}", "success", autoCloseMs=2200)
        else:
            showMessage(self, "GitHub 登录失效", result.message, "warning")

    def _cleanupGithubRefreshThread(self) -> None:
        if self._githubRefreshThread is not None:
            self._githubRefreshThread.deleteLater()
            self._githubRefreshThread = None

    def _logoutGithub(self) -> None:
        session = cached_session_state()
        if not session.session_token:
            self._applyGithubSessionSnapshot()
            return
        if self._githubLogoutThread is not None and self._githubLogoutThread.isRunning():
            return
        self._githubLogoutThread = GithubLogoutThread(session.session_token, self)
        self._githubLogoutThread.resultReady.connect(self._handleGithubLogoutResult)
        self._githubLogoutThread.finished.connect(self._cleanupGithubLogoutThread)
        self._setGithubBusy(True, "正在退出 GitHub 登录...")
        self._githubLogoutThread.start()

    def _handleGithubLogoutResult(self, result: GithubAuthResult) -> None:
        self._setGithubBusy(False)
        self._applyGithubSessionSnapshot()
        if result.success:
            showMessage(self, "已退出 GitHub 登录", "当前访问更新站将恢复为默认额度。", "success", autoCloseMs=2200)
        else:
            showMessage(self, "退出失败", result.message, "warning")

    def _cleanupGithubLogoutThread(self) -> None:
        if self._githubLogoutThread is not None:
            self._githubLogoutThread.deleteLater()
            self._githubLogoutThread = None

    def _releaseFromSelectedRow(self) -> FirmwareRelease | None:
        row = self.releaseTable.currentRow()
        if row < 0:
            return None
        item = self.releaseTable.item(row, 0)
        if item is None:
            return None
        release = item.data(Qt.ItemDataRole.UserRole)
        return release if isinstance(release, FirmwareRelease) else None

    def _currentKind(self) -> str:
        data = self.kindCombo.currentData()
        return str(data or "Power")
    @staticmethod
    def _firmwareBaseUrl() -> str:
        return str(CTX.cfg.firmwareBaseUrl.value or "https://update.hepi.ng").strip().rstrip("/")

    @staticmethod
    def _formatSize(size: int) -> str:
        if size <= 0:
            return "--"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.2f} MB"

    @staticmethod
    def _formatExpiry(timestamp_value: int) -> str:
        if timestamp_value <= 0:
            return "--"
        local_time = time.localtime(timestamp_value)
        return time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    def _applyLocalStyle(self) -> None:
        dark = isDarkTheme()
        panel_bg = "rgba(255, 255, 255, 0.06)" if dark else "rgba(248, 250, 252, 0.88)"
        border = "rgba(255, 255, 255, 0.12)" if dark else "rgba(15, 23, 42, 0.08)"
        self.setStyleSheet(
            self.styleSheet()
            + f"""
            QWidget#versionScrollWidget {{
                background: transparent;
            }}
            QFrame#FirmwareDetailPanel {{
                background: {panel_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            TextEdit {{
                border: 1px solid {border};
                border-radius: 8px;
                padding: 8px;
            }}
            """
        )
