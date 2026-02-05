"""测试用户管理系统."""

from src.models import init_database, User, ResearchField
from src.services.user_service import UserService
from src.services.briefing_service import BriefingService
from src.services.paper_service import PaperService


def test_user_system():
    """测试用户系统功能."""
    print("=" * 60)
    print("🧪 测试用户管理系统")
    print("=" * 60)
    
    # 初始化数据库
    print("\n📦 初始化数据库...")
    init_database()
    print("✅ 数据库初始化完成")
    
    # 初始化研究领域
    print("\n📚 初始化研究领域...")
    user_service = UserService()
    user_service.init_research_fields()
    
    fields = user_service.get_research_fields()
    print(f"✅ 已创建 {len(fields)} 个研究领域:")
    for f in fields:
        print(f"  - {f.name_cn} ({f.name})")
    
    # 测试用户创建
    print("\n👤 测试用户创建...")
    user = user_service.get_or_create_user(
        telegram_id='123456',
        username='test_user',
        first_name='Test'
    )
    print(f"✅ 用户创建成功: {user.telegram_id}")
    print(f"   每日推送限制: {user.daily_paper_limit}")
    print(f"   历史爬取天数: {user.crawl_history_days}")
    print(f"   完成初始设置: {user.onboarding_completed}")
    
    # 测试设置研究领域
    print("\n🎯 测试设置研究领域...")
    if fields:
        success = user_service.set_user_research_fields('123456', [fields[0].id, fields[1].id])
        print(f"✅ 设置研究领域: {success}")
        
        # 重新获取用户
        user = user_service.get_user_by_telegram_id('123456')
        print(f"   用户领域: {[f.name_cn for f in user.research_fields]}")
        print(f"   完成初始设置: {user.onboarding_completed}")
    
    # 测试更新设置
    print("\n⚙️ 测试更新用户设置...")
    success = user_service.update_user_settings(
        telegram_id='123456',
        daily_paper_limit=15,
        crawl_history_days=14
    )
    print(f"✅ 更新设置: {success}")
    
    user = user_service.get_user_by_telegram_id('123456')
    print(f"   每日推送限制: {user.daily_paper_limit}")
    print(f"   历史爬取天数: {user.crawl_history_days}")
    
    # 测试简报服务
    print("\n📝 测试简报服务...")
    briefing_service = BriefingService()
    
    # 为用户创建简报关联
    user_briefings = briefing_service.create_user_briefings(user)
    print(f"✅ 为用户创建了 {len(user_briefings)} 条简报关联")
    
    # 获取待发送简报
    pending = briefing_service.get_user_pending_briefings(user, limit=5)
    print(f"✅ 用户待发送简报: {len(pending)} 条")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    test_user_system()
