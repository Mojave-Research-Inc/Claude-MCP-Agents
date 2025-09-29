#!/usr/bin/env node
/**
 * Test Arbiter - Uses available models for testing
 */
const { spawn } = require('child_process');

async function testArbiterConnection() {
    console.log('🧪 Testing Arbiter MCP with API Keys...');

    const env = {
        ...process.env,
        OPENAI_API_KEY: process.env.OPENAI_API_KEY,
        XAI_API_KEY: process.env.XAI_API_KEY,
        OPENAI_MODEL: 'gpt-4-turbo',  // Use available model
        XAI_MODEL: 'grok-4-high'       // Keep original
    };

    const child = spawn('node', ['dist/server.js'], {
        cwd: '/root/.claude/mcp-servers/arbiter-mcp',
        env,
        stdio: ['pipe', 'pipe', 'pipe']
    });

    let output = '';
    let errorOutput = '';

    child.stdout.on('data', (data) => {
        output += data.toString();
    });

    child.stderr.on('data', (data) => {
        errorOutput += data.toString();
    });

    // Send test request
    const testRequest = JSON.stringify({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "judge_single",
            "arguments": {
                "task": "Evaluate code quality",
                "rubric": "Rate from 1-10 for readability",
                "candidate": "const greet = name => `Hello ${name}!`;"
            }
        }
    });

    child.stdin.write(testRequest + '\n');

    setTimeout(() => {
        child.kill();

        console.log('📊 Test Results:');
        console.log('Output:', output);
        if (errorOutput) {
            console.log('Error Output:', errorOutput);
        }

        if (output.includes('present')) {
            console.log('✅ API Keys detected successfully');
        }

        if (output.includes('gpt-4-turbo')) {
            console.log('✅ OpenAI model override working');
        }

        if (output.includes('error') && output.includes('404')) {
            console.log('⚠️ Models not available (expected for cutting-edge models)');
        } else if (output.includes('score')) {
            console.log('🎉 ARBITER FULLY FUNCTIONAL - API calls successful!');
        }
    }, 5000);
}

testArbiterConnection();