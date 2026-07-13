import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import App from './App';

describe('App', () => {
  it('renders employee conversations and unsupported message placeholder', async () => {
    render(<App />);

    expect((await screen.findAllByText('小王老师')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('沈晓雨')).length).toBeGreaterThan(0);
    expect((await screen.findAllByText('暂不支持的 file 消息')).length).toBeGreaterThan(0);
  });

  it('opens observation configuration panel', async () => {
    render(<App />);

    await userEvent.click(await screen.findByText('观测配置'));

    expect(screen.getByText('观测范围配置')).toBeInTheDocument();
    expect(screen.getByText(/不影响底层通讯录/)).toBeInTheDocument();
  });
});
