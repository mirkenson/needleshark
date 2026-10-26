"""Public editorial routes, independent of the shared posts.json storage."""


def post_path(post):
    section = 'cases' if post.get('kind') == 'case' else 'blog'
    return f'/{section}/{post["slug"]}/'


def post_file(post):
    return post_path(post).lstrip('/') + 'index.html'
