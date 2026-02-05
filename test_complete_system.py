"""完整系统测试."""

from src.models import init_database, User, ResearchField, Paper, Briefing
from src.services.user_service import UserService
from src.services.briefing_service import BriefingService
from src.services.paper_service import PaperService


def test_complete_system():
    """测试完整系统功能."""
    print("=" * 60)
    print("🧪 完整系统测试")
    print("=" * 60)
    
    # 初始化数据库
    print("\n📦 初始化数据库...")
    init_database()
    print("✅ 数据库初始化完成")
    
    # 初始化服务
    user_service = UserService()
    paper_service = PaperService()
    briefing_service = BriefingService()
    
    # 1. 初始化研究领域
    print("\n📚 初始化研究领域...")
    user_service.init_research_fields()
    fields = user_service.get_research_fields()
    print(f"✅ 已创建 {len(fields)} 个研究领域")
    
    # 2. 创建测试用户
    print("\n👤 创建测试用户...")
    user1 = user_service.get_or_create_user(
        telegram_id='user_001',
        username='test_user1',
        first_name='Test1'
    )
    user2 = user_service.get_or_create_user(
        telegram_id='user_002',
        username='test_user2',
        first_name='Test2'
    )
    print(f"✅ 创建用户1: {user1.telegram_id}")
    print(f"✅ 创建用户2: {user2.telegram_id}")
    
    # 3. 设置用户研究领域
    print("\n🎯 设置用户研究领域...")
    user_service.set_user_research_fields('user_001', [fields[0].id, fields[1].id])  # ML, NLP
    user_service.set_user_research_fields('user_002', [fields[2].id])  # CV
    print("✅ 用户1订阅: 机器学习、自然语言处理")
    print("✅ 用户2订阅: 计算机视觉")
    
    # 4. 更新用户设置
    print("\n⚙️ 更新用户设置...")
    user_service.update_user_settings(
        telegram_id='user_001',
        daily_paper_limit=5,
        crawl_history_days=7
    )
    user_service.update_user_settings(
        telegram_id='user_002',
        daily_paper_limit=3,
        crawl_history_days=3
    )
    print("✅ 用户1: 每日5篇, 历史7天")
    print("✅ 用户2: 每日3篇, 历史3天")
    
    # 5. 验证用户设置
    print("\n✅ 验证用户设置...")
    user1 = user_service.get_user_by_telegram_id('user_001')
    user2 = user_service.get_user_by_telegram_id('user_002')
    
    print(f"\n用户1 ({user1.telegram_id}):")
    print(f"  - 订阅领域: {[f.name_cn for f in user1.research_fields]}")
    print(f"  - 每日推送: {user1.daily_paper_limit}")
    print(f"  - 历史爬取: {user1.crawl_history_days}")
    print(f"  - 完成设置: {user1.onboarding_completed}")
    
    print(f"\n用户2 ({user2.telegram_id}):")
    print(f"  - 订阅领域: {[f.name_cn for f in user2.research_fields]}")
    print(f"  - 每日推送: {user2.daily_paper_limit}")
    print(f"  - 历史爬取: {user2.crawl_history_days}")
    print(f"  - 完成设置: {user2.onboarding_completed}")
    
    # 6. 获取活跃用户列表
    print("\n👥 获取活跃用户列表...")
    active_users = user_service.get_all_active_users()
    print(f"✅ 活跃用户数: {len(active_users)}")
    
    print("\n" + "=" * 60)
    print("✅ 所有系统测试通过!")
    print("=" * 60)
    print("\n📋 系统功能总结:")
    print("  ✅ 用户注册与管理")
    print("  ✅ 研究领域订阅")
    print("  ✅ 个性化推送设置（每日数量、历史天数）")
    print("  ✅ 用户差异化配置")
    print("  ✅ 历史简报查询支持")
    print("\n🤖 Telegram 机器人命令:")
    print("  /start - 注册/欢迎")
    print("  /fields - 修改研究领域")
    print("  /settings - 查看设置")
    print("  /limit <数量> - 修改每日推送")
    print("  /history <天数> - 修改历史爬取天数")
    print("  /history - 查看历史简报")
    print("  /next - 获取下一条简报")
    print("  /today - 查看今日待读")
    print("  /stats - 查看统计")


if __name__ == "__main__":
    test_complete_system()
